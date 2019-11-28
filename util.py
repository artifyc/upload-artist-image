import os, shutil, uuid, io, sys, PIL
import logging
from math import floor
from ast import literal_eval
from urllib.parse import unquote_plus
from PIL import Image, ImageDraw, ImageFont 
from transforms import RGBTransform
from lambda_function import lambda_handler as handler
logger = logging.getLogger()
logger.setLevel(logging.INFO)

"""
Cleans up /tmp folder of lambda after execution
But can also be used to clean up any local folder on the lambda 
"""
def cleanup_temp(folder='/tmp'):
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))
            return False
    return True


"""
Validate that the image passed is valid by downloading it from S3 and opening it
with Pillow
Args:
<S3Client> client- the boto3 S3 client.
<str> filename - the name of the file being uploaded.
<str> imgpath - location of file on S3.
Returns:
<bool> - returns whether the image returned was valid.
"""
def validate_image(imgpath, filename, client=None, test=False):
    # this check necessary because may be passed foldernames
    if imgpath.endswith(('.png', '.jpg', '.tiff', '.jpeg')):
            # fetch actual photo and download it to the lambda
            if not test: 
                client.download_file(os.environ["s3_bucket"], imgpath, "/tmp/" + filename)
            try:
                with open(imgpath, 'rb+') as content_file:
                    img = Image.open(io.BytesIO(content_file.read())).convert('RGBA')
                    img.verify()
                    img.close()
                    return True
            except Exception as e:
                logging.info("Image is invalid with exception: {}".format(e))
                return False
    else: return False

"""
Tint the frame such that it becomes the color the customer requested
Args:
<bytesIO> image - image content in a buffer.
<str> color - the color in hexadecimal representation.
Returns:
<bytesIO> image - image content of tinted frame in a buffer.
"""
# TODO: possibly need to convert the gold frame into greyscale
def tint_frame(image, color):

    value = color.lstrip('#')
    lv = len(value)
    converted = tuple(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))

    image = RGBTransform().mix_with((converted),factor=.30).applied_to(image)

    return image
    

# TODO: add encryption?? SSECustomerAlgorithm = AES256 ?
# returns converted file
# def upload_to_new_s3(client, file)
# TODO: add try catches
"""
Uploads transformed image to artist's spot on 
Args:
<S3Client> client- the boto3 S3 client.
<Dict> metadata - image metadata with config info.
<bytesIO> image - image buffer.
<int> size - base width used to the resize process.
Returns:
<bytesIO> buffer - returns the image content resized.
"""
def upload_image(client, metadata, image, size):
    # first fetch actual object
    logging.info(size)
    size = "small" if "225" in size else "medium"
    prefix = 'users/' + metadata['artist-uuid'] + '/' + metadata['commission-type'] + '/' + size + '/'

    img_id = uuid.uuid4()

    response = client.put_object(
        Body=image.getvalue(),
        Bucket=os.environ["s3_bucket"],
        Key=prefix + str(img_id) + ".jpeg"
    )

    logging.info("picture written to {}/{}".format(os.environ["s3_bucket"], prefix))
    return response

# TODO: add try catches
# TODO: add situation where crop fails, create white image with question mark and upload that
# initiate method failure_image for above situation
# check dimensions to add whitespace after crop
"""
Resizes proportionally an image using `size` as the base width.
Args:
<S3Client> client- the boto3 S3 client.
<str> filename - the name of the file being uploaded.
<int> size - base width used to the resize process.
<Dict> metadata - image metadata with config info.
Returns:
<bytesIO> buffer - returns the image content resized.
"""
def convert_and_resize_portfolio_image(client, filename, size, metadata):

    path = "/tmp/" + filename
    with open(path, 'rb+') as content_file:

        # size of the image-to-be as dicatated by the os.environ variable
        tuple_environ_size = literal_eval("({})".format(size))

        environ_width, environ_height = size.split(',')
        content = content_file.read()
        img = Image.open(io.BytesIO(content)).convert('RGBA')

        width, height = img.size   # Get dimensions

        crop_map = {"left": metadata['crop-left'], "top": metadata['crop-top'],\
         "right": metadata['crop-right'], "bottom": metadata['crop-bottom']}

        # crop the image given the inputs of the user
        # resize image to be the input size
        # the size appears as "225, 300", literally eval as a tuple for size

        image = img.crop((int(crop_map["left"]), int(crop_map["top"]),\
         int(crop_map["right"])+width, int(crop_map["bottom"])+height))

        # after cropping get a new image the size of the buffer and fill with white
        whitespace = Image.new('RGBA', tuple_environ_size, (0, 0, 0, 0))

        # crop image while maintaining its aspect ratio
        image.thumbnail(tuple_environ_size, PIL.Image.NEAREST)

        centered_width = ((int(environ_width) - width)/2)
        centered_height = ((int(environ_height) - height)/2)

        # smush image.thumbnail over whitespace so that any extra space is white
        image = whitespace.paste(image, (centered_width, centered_height))

        buffer = io.BytesIO()
        format = 'PNG'

        image.save(buffer, format, quality=90)

        return image
        
# TODO: add try catches
"""
Watermarks medium size images with `Artifyc`.
Args:
<bytesIO> buffer - image content in a buffer.
<str> filename - the name of the file being uploaded.
<Dict> metadata - image metadata with config info.

Returns:
<bytesIO> buffer - returns the image content resized.
"""
def watermark_image_with_text(buffer, filename, metadata, text="Artifyc"):

    imageWatermark = Image.new('RGBA', buffer.size, (255, 255, 255, 0))

    draw = ImageDraw.Draw(imageWatermark)
    path = os.environ['font_path'] + 'Raleway-Bold.ttf'
    
    width, height = buffer.size
    small_map = {'bottom': 5, 'middle': 2, 'top': 1.10}

    height_margin = small_map[metadata['watermark-location']]

    font = ImageFont.truetype(font=path, size=36, index=0)
    textWidth, textHeight = draw.textsize(text, font)

    x = (width - textWidth)/2
    y = (height - textHeight)/height_margin

    # add opacity to text with 128 = 50% opacity
    draw.text((x, y), text, "#ffffff", font, fill=(255,255,255,128))

    image = Image.alpha_composite(buffer, imageWatermark).convert('RGB')

    image.save(io.BytesIO(), format='JPEG', quality=90)
    return buffer

# alpha_composite frame over image, create 
# small frame thickness: 7 px left
#                       8 px top
#                       8 px right
#                       9 px bottom
# medium frame thickness: 17 px top
#                         14 px left 
#                         14 px right
#                        18px bottom
# read frame from S3
"""
Watermarks medium size images with `Artifyc`.
Args:
<bytesIO> buffer - image content in a buffer.
<str> size - variable dictating size of the image (small or med).
<S3Client> client - the boto3 S3 client.
<str> color - metadata variable indicating color of the frame.

Returns:
<bytesIO> buffer - returns the image content with a frame.
"""
def place_frame_over_image(buffer, size, client, color=None):
    # determine whether to use med or small frame
    filename = "framemed.png" if "med" in size else ""
    path = "assets/frames/" + filename

    #TODO: figure out how to tint the frame color based on passed color
    with open(path, 'rb+') as content_file:
        content = content_file.read()
        frame = Image.open(io.BytesIO(content)).convert('RGBA')

        if color is not None: frame = tint_frame(frame, color)

        framed_image = Image.alpha_composite(buffer, frame).convert('RGB')

        framed_image.save(io.BytesIO(), 'JPEG', quality=90)

        return framed_image