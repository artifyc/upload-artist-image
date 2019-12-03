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

    logging.info("Entered portfolio method...")
    # only watermark if it's medium, smaller images do not need to be watermarked
    for size in [s for s in os.environ if "width" in s]:

        # convert and crop all images
        image_buffer = convert_and_resize_portfolio_image(client, filename, os.environ[size], metadata, local=local, test=test)

        # watermark logic
        if "med" in size and metadata['watermark'] is True: image_buffer = watermark_image_with_text(image_buffer, filename, metadata, local=local)

        # framing logic
        if "frame-color" in metadata and metadata["frame"]: image = place_frame_over_image(image_buffer, size, metadata["frame-color"], local)  
        elif metadata["frame"]: image = place_frame_over_image(image_buffer, size, client)
        else: pass

        response = upload_image(client, metadata, image, size)
        logging.info(response)

    # delete buffered files from /S3
    # note, can remove this directory or will the lambda freak out?
    # may have to remove files individually
    if not local: cleanup_temp()
    response = client.delete_object(os.environ["s3_bucket"], key)

    return
    
# for profile image
# convert img to png + resize to circle or at least 125 x 125px
# upload to S3 under path os.environ["s3_bucket"]/users/artist-uuid/profile.jpg
# delete img from buffer and from local 
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


"""
If any issue occurs during the processing of the image, the program
will catch the error and execute this, putting a "wrong" image???
This wrong image should be stored on the lambda. @ KYLE should this be implemented??
Args:
"""
# TODO: add situation where crop fails
# check dimensions to add blackspace
#def failure_image:
    #return