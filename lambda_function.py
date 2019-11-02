import json
import boto3
import uuid
import os
from botocore.exceptions import ClientError
import constants as cnst
from boto3.dynamodb.conditions import Key, Attr
from PIL import Image
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Steps:
#   Check if image exists on S3 Buffer directory.   (TRY CATCH)
#        If doesn't exist, return with error. Else continue
#   Grab User metadata from Users Table             (TRY CATCH)
#       if User doesn't exist, return with error. Else continue
#   From user object grab S3 Image Path             (TRY CATCH)
#   Grab amount of data user has saved              (TRY CATCH)
#   Check if user is not going over max allowed data stored
#   Download image                                  (TRY CATCH)
#   Transform image as needed                       (TRY CATCH)
#   Store file onto s3                              (TRY CATCH)
#   Delete image from buffer directory              (TRY CATCH - Trigger alert or send to queue for manual/retry deletion or have
                                  # a job that triggers to cleanup buffer regularly)
# Upload Image metadata
# Update user metadata if needed

# KYLE PUT YOUR SHIT INTO METHODS I DON'T WANT ANY BELTON ZHONG CODE IN THIS BITCH

def lambda_handler(event, context):

    bucket_path = "/upload-buffer/temp-bucket-299211192/"
    dynamo = boto3.resource('dynamodb')

    s3 = boto3.client('s3')
    bucket = cnst.user_images_bucket_name
    table_name = cnst.users_table_name
    #file_name = event['file_name']

    check_images(s3, bucket_path)

    return {
        'statusCode': 200,
        'body': json.dumps('Conversion Executed OK')
    }

  # Check if image exists on S3 Buffer Directory
    file_key = cnst.s3_images_buffer_key + "/"+file_name
    try:
        # Amazon S3/artifyc-user-images-qa/upload-buffer/logo.png

        s3.head_object(Bucket=cnst.user_images_bucket_name, Key=file_key)
    except ClientError as e:
        # Not found
        print(e)
        return "Error Occurred Queryimg for image in buffer"

    # Get user path from dynamodb for s3. Also Check if user exists
    user_id = event['user_id']
    table = dynamo.Table('Users')

    try:

        user_object = table.query(
            KeyConditionExpression=Key('user_id').eq(user_id)
        )
        print(user_object)
        user_image_s3_path = user_object['Items'][0]['s3_images_path']
    except ClientError as e:
        print(e)
        return e
        # Error Occurred

    # Get s3 key from user_info
    # user_image_s3_path = user_object['s3_images_path']

    # Download Image
    try:
        image = s3.get_object(
            Bucket=cnst.user_images_bucket_name, Key=file_key)
    except ClientError:
        return "Error occurred downloading image"
    print(image)

    # Transform Image using PILLOW

    # Move image from buffer directory to user's image directory if it doesn't go over size limit
    try:
        s3.upload_file(image, bucket, user_image_s3_path)
    except ClientError:
        pass
    return "early cut off test"
    # Upload image metadata
    image_id = "test"

    # Generate UUID for image

    dynamo.put_item(
        Table_Name='',
        Item={
            'user_id': {'S': user_id},
            'image_id': {'S': image_id},
            'uploaded_timestamp': {'S': current_timestamp},
            'tags': {'S': tags_list},
        }
    )

    # Might need to query user to get timestamp from user db before updating.
    # Or redo user with no sort key

    # Update user metadata if needed
    dynamo.update_item(
        Table_Name='',
        Key={
            'user_id': '',
        },
        AttributeUpdates={
            'yeet': '123',
        }
    )

    return {
        'statusCode': 200,
        'body': json.dumps('Image Successfully Uploaded!')
    }

# check image path name, see if it's jpg, if it is, return the path
# otherwise, convert and reupload with new name, return path
# todo: add try-catches

# client = s3 client previously created
# prefix = the filepath within the buffer bucket with particular user's data
# delimiter = "/"

def check_images(client, prefix):


    response = client.list_objects_v2(
        Bucket=cnst.user_images_bucket_name,
        Delimiter="/",
        Prefix=prefix
    )

    logging.info("found images {} in bucket {}".format(response['Contents'], cnst.user_images_bucket_name))

    # parse through responded files
    # s3 is fucking stupid and returns the folder as an object
    # if the key ends with a filetype that needs conversion, convert it
    for file in response['Contents']:
        if file['Key'].endswith(('.png', '.jpeg', '.tiff')):
            convert(client, prefix, file['Key'])

    # all files converted
    return True

# todo: add encryption SSECustomerAlgorithm = AES256 ?
# returns converted file


def convert(client, prefix, filename):

    # first fetch actual object
    response = client.get_object(
        Bucket=cnst.user_images_bucket_name,
        Key=prefix + filename
    )

    logging.info("photo fetched: {}".format(response))

    img_id = uuid.uuid4()

    image = Image.open(response['Body'])
    rgb_im = image.convert('RGB')
    rgb_im.save('{}.jpg'.format(img_id))

    response = client.put_object(
        Body=rgb_im,
        Bucket=cnst.user_images_bucket_name,
        Key=prefix + img_id
    )

    logging.info("photo uploaded: {}".format(response))

    return True
