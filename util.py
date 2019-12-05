import os, shutil, uuid, io, sys, numbers
if os.environ.get("s3_bucket") is not None: import boto3
import logging
from math import floor
from ast import literal_eval
from urllib.parse import unquote_plus
from transforms import RGBTransform
from PIL import Image, ImageDraw, ImageFont 
logger = logging.getLogger()
logger.setLevel(logging.INFO)


# alpha_composite frame over image, create 
# small frame thickness: 7 px left
#                       8 px top
#                       8 px right
#                       9 px bottom
# medium frame thickness: 17 px top
#                         14 px left 
#                         14 px right
#                        18px bottom

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
            print('Failed to delete {}. Reason: {}'.format(file_path, e))
            return False
    return True


"""
Validates image in one of two ways:
1. Validates that the image passed is valid by downloading it from S3 and opening it with Pillow
2. If an Image object is sent to the function, merely verify that image and return True or False
Args:
<str> imgpath - location of file on S3.
<str> filename - the name of the file being uploaded.
<Image> image - optional Image object to verify.
<S3Client> client- the boto3 S3 client.
<bool> local - indicates whether this method is being run locally or on a lambda.

Returns:
<bool> - returns whether the image returned was valid.
"""
def validate_image(imgpath=None, filename=None, image=None, client=None, local=False):
    # this check necessary because may be passed foldernames
    if image:
        try:
            image.verify()
            return True
        except Exception as e:
            logging.info("\tImage is invalid with exception: {}".format(e))
            return False

    if imgpath.endswith(('.png', '.jpg', '.tiff', '.jpeg')):
            # fetch actual photo and download it to the lambda
            if not local: 
                client.download_file(os.environ["s3_bucket"], imgpath, "/tmp/" + filename)
            try:
                with open(imgpath, 'rb+') as content_file:
                    img = Image.open(io.BytesIO(content_file.read())).convert('RGBA')
                    img.verify()
                    img.close()
                    return True
            except Exception as e:
                logging.info("\tImage is invalid with exception: {}".format(e))
                return False
    else: return False


"""
Tint the frame such that it becomes the color the customer requested
On failure default to gold frame
Args:
<bytesIO> image - image content in a buffer.
<str> color - the color in hexadecimal representation.
<bool> local - indicates whether this method is being run locally or on a lambda.
Returns:
<bytesIO> image - image content of tinted frame in a buffer.
"""
# TODO: possibly need to convert the gold frame into greyscale
def tint_frame(image, color, size, local=False):
    try:
        value = color.lstrip('#')
        lv = len(value)
        converted = tuple(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))

        image = RGBTransform().mix_with((converted),factor=.30).applied_to(image)

    except Exception as e:
        logging.info("\ttint_frame failed with exception: {}. Falling back to gold...".format(e))
        path = "assets/assets/frames/gold/" if local else "assets/frames/gold/"
        filename = "framemed.png" if "med" in size else "framesmall.png"

        # open regular gold frame file
        with open(path + filename, 'rb+') as content_file:
            image = Image.open(io.BytesIO(content_file.read())).convert('RGBA')

    return image
    

# TODO: add encryption in flight?? SSECustomerAlgorithm = AES256 ?
# returns converted file
# def upload_to_new_s3(client, file)
# TODO: add try catches
"""
Uploads transformed image to artist's folders on S3
Args:
<S3Client> client- the boto3 S3 client.
<Dict> metadata - image metadata with config info.
<bytesIO> image - image buffer.
<int> size - base width used to the resize process.
<int> tries - number of attempts at this method.
Returns:
<bytesIO> buffer - returns the image content resized.
"""
def upload_image(client, metadata, image, size, tries=1, local=False):
    # input validations:
    try:
        if not metadata or not metadata['artist-uuid'] or not metadata['commission-type'] or not metadata['name']:
            logging.info("\tInvalid metadata passed into upload_image")
            raise ValueError

        if size.split("_")[1] not in {"medium", "small"}: 
            logging.info("\tInvalid size passed into upload_image")
            raise ValueError

        if image is None: 
            logging.info("\tAbsolutely wack image passed into upload_image")
            raise ValueError

        if tries > 3:
            logging.info("\tInvalid number of tries in this bitch")
            raise RuntimeError

        buffer = io.BytesIO()
        if image.mode != 'RGB': image = image.convert('RGB')
        image.save(buffer, 'JPEG', quality=90)

        prefix = 'users/' + metadata['artist-uuid'] + '/' + metadata['commission-type'] + '/' + size + '/'

        if local:
            image.save("tests/tests/upload_image_test/out/{}.jpeg".format(metadata['name']), "JPEG") 
            return True
        else:
            response = client.put_object(
                Body=buffer.getvalue(),
                Bucket=os.environ["s3_bucket"],
                Key=prefix + metadata['name'] + ".jpeg"
            )
            logging.info("\tPicture uploaded to {}/{}".format(os.environ["s3_bucket"], prefix))
            return response
        
    except Exception as e:
        if tries < 3: 
            return upload_image(client, metadata, image, size, tries+1)
        elif tries >= 3: 
            logging.info("\tUpload to S3 bucket and 3 retries failed with exception {}".format(e))
            return False, e
        return response


# TODO: add situation where crop fails, create white image with question mark and upload that (???)
# initiate method failure_image for above situation
# check dimensions to add whitespace after crop
"""
Resizes proportionally an image using `size` as the base width.
Args:
<S3Client> client- the boto3 S3 client.
<str> filename - the name of the file being uploaded.
<int> size - base width used to the resize process.
<Dict> metadata - image metadata with config info.
<bool> local - indicates whether this method is being run locally or on a lambda.
<bool> test - indicates whether this is a test.
Returns:
<bytesIO> buffer - returns the image content resized.
"""
def convert_and_resize_portfolio_image(filename, metadata, size, client=None, local=False, test=False):
    # input validations:
    # verify that all metadata crop coordinates are integers
    try:
        if not all([isinstance(x, numbers.Number) for x in (metadata['crop-left'], metadata['crop-right'], metadata['crop-top'], metadata['crop-bottom'])]): raise ValueError

        # if this is being run on the lambda and is not a test:
        if not local and not test: path = "/tmp/" + filename
        # if we are running locally and testing, use the testing directory
        elif not local and test: path = "tests/convert_and_resize_test/" + filename
        # if we are running a test from the lambda, use this directory
        else: path = "tests/tests/convert_and_resize_test/" + filename

        # validate_image(imgpath=None, filename=None, image=None, client=None, local=False)
        if not validate_image(imgpath=path, filename=filename, client=client, local=local):
            logging.info("\tInvalid image passed into convert_and_resize")
            raise TypeError

        with open(path, 'rb+') as content_file:
            image = Image.open(io.BytesIO(content_file.read())).convert('RGBA')
 
            # size of the image-to-be as dicatated by the os.environ variable
            tuple_environ_size = literal_eval("({})".format(size))

            environ_width, environ_height = size.split(',')
            width, height = image.size   # Get dimensions

            if not all([(x == 0 for x in (metadata['crop-left'], metadata['crop-right'], metadata['crop-top'], metadata['crop-bottom']))]):
                image = image.crop((int(metadata['crop-left']), int(metadata['crop-top']), int(metadata['crop-right'])+width, int( metadata['crop-bottom'])+height))
            # after cropping get a new image the size of the buffer and fill with white
            whitespace = Image.new('RGBA', tuple_environ_size, (255, 255, 255, 255))

            # crop image while maintaining its aspect ratio
            image.thumbnail(tuple_environ_size, Image.NEAREST)
            width, height = image.size   # Get dimensions

            centered_width = floor(((int(environ_width) - width)/2))
            centered_height = floor(((int(environ_height) - height)/2))

            # smush image.thumbnail over whitespace so that any extra space is white
            whitespace.paste(image, (centered_width, centered_height))
                
    except Exception as e:
        logging.info("\tconvert_and_resize failed with exception {}".format(e))
        return False, e

    return whitespace
        

"""
Watermarks medium size images with `Artifyc`.
Args:
<bytesIO> buffer - image content in a buffer.
<str> filename - the name of the file being uploaded.
<Dict> metadata - image metadata with config info.
<str> text - text words to be watermarked, defaults to `Artifyc`
<bool> local - indicates whether this method is being run locally or on a lambda.
Returns:
<bytesIO> buffer - returns the image content resized.
"""
def watermark_image_with_text(image, metadata, text="Artifyc", local=False):
    try: 
        imageWatermark = Image.new('RGBA', image.size, (255, 255, 255, 0))

        draw = ImageDraw.Draw(imageWatermark)

        path = os.environ['font_path'] + 'Raleway-Bold.ttf' if not local else "fonts/fonts/Raleway-Bold.ttf"
        
        width, height = image.size
        small_map = {'top': 10, 'middle': 2, 'bottom': 1.10}

        height_margin = small_map[metadata['watermark-location']]

        font = ImageFont.truetype(font=path, size=64, index=0)
        textWidth, textHeight = draw.textsize(text, font)

        x = (width - textWidth)/2
        y = (height - textHeight)/height_margin

        # add opacity to text with 128 = 50% opacity
        draw.text((x, y), text, font=font, fill=(255,255,255,128))

        # returns image formatted as RBGA (aka PNG)
        image = Image.alpha_composite(image, imageWatermark)

    except Exception as e:

        logging.info("\twatermark_image_with_text failed with error {}".format(e))
        return False, e

    return image

"""
Frames our user-submitted images in relatively colored frames,
if there is a failure, it will default to a gold frame.
Args:
<bytesIO> image - image content in a buffer.
<str> size - variable dictating size of the image (small or med).
<str> color - metadata variable indicating color of the frame.
<bool> local - indicates whether this method is being run locally or on a lambda.
Returns:
<bytesIO> buffer - returns the image content with a frame.
"""
def place_frame_over_image(image, size, color=None, local=False):
    # determine whether to use med or small frame
    try:
        filename = "framemed.png" if "med" in size else "framesmall.png"
        backup_path = "assets/frames/gold/" + filename if not local else "assets/assets/frames/gold/"
        path = "assets/frames/greyscale/" + filename if not local else "assets/assets/frames/greyscale/"
        image.convert('RGBA')
        final_path = backup_path if color is None else path 

        with open(final_path + filename, 'rb+') as content_file:
            content = content_file.read()
            frame = Image.open(io.BytesIO(content)).convert('RGBA')

            if color is not None: frame = tint_frame(frame, color, size, local)
            framed_image = Image.alpha_composite(image, frame)

            #buffer = io.BytesIO()
            #framed_image.save(buffer, 'JPEG', quality=90)
            return framed_image

    except Exception as e:
        logging.info("\tplace_frame_over_image failed with exception: {} - {}".format(type(e).__name__, e))
        return False, e