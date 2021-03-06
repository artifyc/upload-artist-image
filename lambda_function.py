import json, uuid, os, io, sys, logging, argparse
if os.environ.get("s3_bucket") is not None: import boto3
#from botocore.exceptions import ClientError
from util import *
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Steps:
# obtain metadata from event photo file
# if portfolio, trigger portfolio workflow
#   1. convert image
#   2. watermark image and place watermark as requested
#   3. convert the image to consistent sizing, fill in any extra space with whitespace
#   4. if framing the image and a color has been chosen, convert the frame color
#   5. superimpose the frame around the edges of the image
#   6. upload the final images to S3 under /upload-final/artistuuid/commissiontype/ key
#   7. delete images from upload buffer, delete images from /tmp
#   8. update dynamodb to have paths of each image

# if profile image, trigger profile image workflow
# if delivery, handle delivery workflow

def lambda_handler(event, context, test=False, local=False):

    client = boto3.client('s3')
    for file in event['Contents']:
        # parse the filename from the key
        filename = file['Key'].split("/")[len(file['Key'].split("/"))-1]
        if validate_image(file['Key'], filename, client):
            response = client.head_object(Bucket=os.environ["s3_bucket"], Key=file['Key'])
            # this will just dynamically run the below method that corresponds with what mode the uploaded picture has
            getattr(sys.modules[__name__], "handle_%s" % response['Metadata']['mode'])(client, file['Key'], filename, response['Metadata'])

    return {
        'statusCode': 200,
        'body': json.dumps('Image Successfully Uploaded!')
    }

"""
Resizes proportionally an image using `size` as the base width.
Args:
<S3Client> client- the boto3 S3 client.
<str> key - the path in s3 to the JPG bring processed.
<Dict> metadata - image metadata with config info.
Returns:
None ???
"""
def handle_portfolio(client, key, filename, metadata, local=False, test=False):
    try:
        if local: 
            os.environ["width_small"] = "225,300"
            os.environ["width_medium"] = "415,615"
            os.environ["s3_bucket"] = "fake-bitch"
        logging.info("Entered portfolio method...")

        if not key: raise ValueError("key passed had value of None")
        if not client: raise ValueError ("no client passed to handle portfolio method")

        # only watermark if it's medium, smaller images do not need to be watermarked
        for size in [s for s in os.environ if "width" in s]:

            # convert and crop all images
            converted_img = convert_and_resize_portfolio_image(filename, metadata, os.environ[size], client=client, local=local, test=test)
            if type(converted_img) == tuple: 
                raise ValueError('convert and resize portfolio image failed with exception: {}'.format(converted_img[1]))
            logging.info("\tconversion + resize successful")
            
            # watermark logic
            if "medium" in size and metadata['watermark'] == 'True': 
                watermarked_img = watermark_image_with_text(converted_img, metadata, local=local)
                if type(watermarked_img) == tuple: 
                    raise ValueError('watermarking image failed with exception: {}'.format(watermarked_img[1]))
            else: 
                watermarked_img = converted_img
            logging.info("\twatermark successful")

            # framing logic
            if "frame-color" in metadata and metadata["frame"]: framed_img = place_frame_over_image(watermarked_img, size, metadata["frame-color"], local)  
            elif metadata["frame"]: framed_img = place_frame_over_image(watermarked_img, size, client)
            else: pass
            if type(framed_img) == tuple: 
                raise ValueError('framing image failed with exception: {}'.format(framed_img[1]))
            logging.info("\tframing successful")

            response = upload_image(client, metadata, framed_img, size, local=local)
            if type(response) == tuple: 
                raise ValueError('uploading image failed with exception: {}'.format(response[1]))
            logging.info("\tuploading successful")

        # delete buffered files from /S3 only on local
        # note, can remove this directory or will the lambda freak out?
        # may have to remove files individually
        if not local: 
            cleanup_temp()
            response = client.delete_object(
                Bucket=os.environ["s3_bucket"],
                Key=key + metadata["name"] + ".jpeg"
            )
        if local:
            del os.environ["width_small"]
            del os.environ["width_medium"]
            del os.environ["s3_bucket"]

    except Exception as e:
        logging.info("\thandle portfolio failed with exception: {} - {}".format(type(e).__name__, e))
        return False, e

    return True
    
# for profile image
# convert img to png + resize to circle or at least 125 x 125px
# upload to S3 under path os.environ["s3_bucket"]/users/artist-uuid/profile.jpg
# delete img from buffer and from local 
def handle_profile():
    return

# TODO

# literally this just gets uploaded to S3 under the correct bucket / author name
def handle_delivery():
    return

    # client = s3 client previously created
    # prefix = the filepath within the buffer bucket with particular user's data
    # delimiter = "/"