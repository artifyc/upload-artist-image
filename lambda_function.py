import json
import boto3
import uuid
import os
import io
import sys
from botocore.exceptions import ClientError
import constants as cnst
from boto3.dynamodb.conditions import Key, Attr
from urllib.parse import unquote_plus
import PIL
from PIL import Image, ImageDraw, ImageFont 
from PIL.Image import core as _imaging
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

'''
SAMPLE PAYLOAD FOR IMAGE UPLOAD EVENT
'{"ResponseMetadata":
    {"RequestId": "9F112A3FC0DF4BF0",
    "HostId": "c8oYc6QCgtTSChKmz/EqR3cSjARDUx7rPx3TsdjHErDHz/xljlLOsxssjgNYWV2216T9lIuMhEA=",
    "HTTPStatusCode": 200,
    "HTTPHeaders":
        {"x-amz-id-2": "c8oYc6QCgtTSChKmz/EqR3cSjARDUx7rPx3TsdjHErDHz/xljlLOsxssjgNYWV2216T9lIuMhEA=",
        "x-amz-request-id": "9F112A3FC0DF4BF0",
        "date": "Wed, 13 Nov 2019 02:07:16 GMT",
        "x-amz-bucket-region": "us-east-1",
        "content-type": "application/xml",
        "transfer-encoding": "chunked",
        "server": "AmazonS3"},
    "RetryAttempts": 0},
    "IsTruncated": "False",
    "Contents": [
        {
            "Key": "upload-buffer/temp-bucket-299211192/",
            "LastModified": "datetime.datetime(2019, 10, 29, 23, 34, 29, tzinfo=tzlocal())",
            "ETag": "d41d8cd98f00b204e9800998ecf8427e",
            "Size": 0,
            "StorageClass": "STANDARD"
        },
        {
            "Key": "upload-buffer/temp-bucket-299211192/kaz.png",
            "LastModified": "datetime.datetime(2019, 11, 13, 2, 7, 14, tzinfo=tzlocal())",
            "ETag": "ee72b223ba8463ba5e1b42ca1662ab8f",
            "Size": 102883,
            "StorageClass": "STANDARD"}
    ],
    "Name": "artifyc-user-images-qa",
    "Prefix": "upload-buffer/temp-bucket-299211192/",
    "Delimiter": "/",
    "MaxKeys": 1000,
    "EncodingType": "url",
    "KeyCount": 3
}'
'''

# Steps:
# obtain metadata from event photo file
# if portfolio, trigger portfolio workflow
# 1. convert image
# 2. watermark image and place watermark as requested
# 3. convert the image to consistent sizing
# 4. if framing the image, convert the frame color
# 5. superimpose the frame around the edges of the image
# 6. upload the final images to S3 under /upload-final/artistuuid/commissiontype/ key
# 7. delete image from upload buffer
# 8. update dynamodb to have paths of each image

# if profile image, trigger profile image
# if delivery, handle delivery

# I DON'T WANT ANY BELTON ZHONG CODE IN THIS BITCH


def lambda_handler(event, context):

    client = boto3.client('s3')

    # the bucket name will always get listed as being in the contents
    # below we narrow just so that we're obtaining the image
    for file in event['Contents']:
        if file['Key'].endswith(('.png', '.jpg', '.tiff')):
            response = client.head_object(Bucket=os.environ["s3_bucket"], Key=file['Key'])
            getattr(sys.modules[__name__], "handle_%s" % response['Metadata']['mode'])(file['Key'], response, client)

    # this will just dynamically run the below method
    # that corresponds with what mode the uploaded picture has

    return {
        'statusCode': 200,
        'body': json.dumps('Image Successfully Uploaded!')
    }

# Uploading Portfolio Images 
#   if portfolio, trigger portfolio workflow
#       1. convert image
#       2. watermark image and place watermark as requested
#       3. convert the image to consistent sizing
#       4. if framing the image, convert the frame color
#       5. superimpose the frame around the edges of the image
#       6. upload the final images to S3 under /upload-final/artistuuid/commissiontype/ key
#       7. delete image from upload buffer
#       7(1/2). delete image from /tmp/ on the lambda
#       8. update dynamodb to have paths of each image

def handle_portfolio(key, metadata, client):

    logging.info("Entered portfolio method...")
    # parse the filename from the key
    filename = key.split("/")[len(key.split("/"))-1]
    logging.info(filename)
    # fetch actual photo and download it to the lambda
    client.download_file(os.environ["s3_bucket"], key, "/tmp/" + filename)
    
    # step 1. converting + resize image
    for size in [s for s in os.environ if "width" in s]:
            logging.info(os.environ[size])
            image_buffer = convert_and_resize_image(client, filename, os.environ[size])
            image_buffer = watermark_image_with_text(image_buffer, filename, "#000000", "Helvetica.ttf")
            response = upload_image(client, metadata, image_buffer, os.environ[size])

            logging.info(response)
    

def handle_profile():
    return

# TODO


def handle_delivery():
    return

    # check image path name, see if it's jpg, if it is, return the path
    # otherwise, convert and reupload with new name, return path
    # todo: add try-catches

    # client = s3 client previously created
    # prefix = the filepath within the buffer bucket with particular user's data
    # delimiter = "/"


# todo: add encryption?? SSECustomerAlgorithm = AES256 ?
# returns converted file
# def upload_to_new_s3(client, file)

def upload_image(client, metadata, image, size):
    # first fetch actual object
    logging.info(size)
    prefix = os.environ['Bucket'] + '/upload-final/' + metadata['artist-uuid'] + '/' + metadata['commission-type'] + '/' + size + '/'

    imgByteArr = io.BytesIO()
    image.save(imgByteArr)
    imgByteArr = imgByteArr.getvalue()

    img_id = uuid.uuid4()

    response = client.put_object(
        Body=imgByteArr.getvalue(),
        Bucket=os.environ["s3_bucket"],
        Key=prefix + str(img_id) + ".jpeg"
    )

    return response

def watermark_image_with_text(buffer, filename, color, fontfamily, text="Artifyc"):

    imageWatermark = Image.new('RGB', buffer.size, (255, 255, 255, 0))

    draw = ImageDraw.Draw(imageWatermark)
    
    width, height = buffer.size
    margin = 10
    font = ImageFont.truetype(fontfamily, int(height / 20))
    textWidth, textHeight = draw.textsize(text, font)
    x = width - textWidth - margin
    y = height - textHeight - margin

    draw.text((x, y), text, color, font)

    return Image.alpha_composite(buffer, imageWatermark)

def convert_and_resize_image(client, filename, size):
    """
    Resizes proportionally an image using `size` as the base width.
    Args:
    <bytesIO> body - the image content in a buffer.
    <str> extension - the image extension.
    <int> size - base width used to the resize process.
    Returns:
    <bytesIO> buffer - returns the image content resized.
    """
    path = "/tmp/" + filename
    with open(path, 'rb+') as content_file:

        content = content_file.read()
        img = Image.open(io.BytesIO(content)).convert('RGB')

        wpercent = (float(size) / float(img.size[0]))
        hsize = int((float(img.size[1]) * float(wpercent)))
        img = img.resize((int(size), hsize), PIL.Image.ANTIALIAS)

        buffer = io.BytesIO()
        format = 'JPEG'

        img.save(buffer, format)

        return img
