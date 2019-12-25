import os, shutil, uuid, io, sys, numbers, configparser
if os.environ.get("s3_bucket") is not None: import boto3
import logging
from math import floor
from ast import literal_eval
from urllib.parse import unquote_plus
from transforms import RGBTransform
from PIL import Image, ImageDraw, ImageFont, ImageOps
logger = logging.getLogger()
logger.setLevel(logging.INFO)
config = configparser.ConfigParser()


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

"""
def delete_file(client, key, metadata):
    return client.delete_object(
        Bucket=os.environ["s3_bucket"],
        Key=key + metadata["name"] + ".jpeg"
    )

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
def validate_image(key=None, bucket=None, filename=None, image=None, client=None, local=False):
    # this check necessary because may be passed foldernames
    if image:
        try:
            image.verify()
            return True
        except Exception as e:
            logging.info("\tImage is invalid with exception: {}".format(e))
            return False

    if key.endswith(config['DEFAULT']['valid_filepaths']):
            # fetch actual photo and download it to the lambda
            if not local: 
                client.download_file(bucket, key, config['DEFAULT']['image_path'] + filename)
            try:
                with open(key, 'rb+') as content_file:
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
        path = config["DEFAULT"]["asset_dir_local"] if local else config["DEFAULT"]["asset_dir_lambda"]
        filename = config["DEFAULT"]["medium_frame"] if "medium" in size else config["DEFAULT"]["small_frame"]

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
def upload_image(client, metadata, image, mode, size=None, tries=1, local=False):
    # input validations:
    try:
        if not metadata or not metadata['artist-uuid']:
            logging.info("\tInvalid metadata passed into upload_image")
            raise ValueError

        if size is not None and size not in {config["DEFAULT"]["medium"], config["DEFAULT"]["small"], config["DEFAULT"]["profile_size"]}: 
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

        bucket = os.environ['orders_bucket'] if mode == 'delivery' else os.environ['users_bucket']

        #TODO: rewrite this to handle other types like portfolio images,
        # portfolio has 2 paths, one for each size
        # aria is the small circular image in the top right corner of the navbar
        # profile image is the square img embedded in the profile 
        if "portfolio" in mode and size == config["DEFAULT"]["small"]:
            path = '/users/' + metadata['artist-uuid'] + '/' + metadata['commission-type'] + '/search/' + uuid.uuid4()
        elif "portfolio" in mode and size == config["DEFAULT"]["medium"]:
            path = '/users/' + metadata['artist-uuid'] + '/' + metadata['commission-type'] + '/expanded/' + uuid.uuid4()
        elif "profile" in mode:
            path = '/users/' + metadata['artist-uuid'] + '/profile'
        elif "aria" in mode:
            path = '/users/' + metadata['artist-uuid'] + '/aria'

        else:
            path = '/orders/' + metadata['order-uuid'] + '/' + metadata['name']

        if local:
            image.save(config["DEFAULT"]["upload_test"] + "{}.jpeg".format(metadata['name']), "JPEG") 
            return True

        else:
            response = client.put_object(
                Body=buffer.getvalue(),
                Bucket=bucket,
                Key=path + '.jpeg'
            )
            logging.info("\tPicture uploaded to {}/{}".format(bucket, path))
            return response
        
    except Exception as e:
        #logging.info("\tUpload to S3 bucket failed with exception {}, retrying...".format(e))
        if tries < 3: 
            #logging.info("Upload to S3 bucket failed with exception {}. Try number {}".format(e, tries))
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
def convert_and_resize_portfolio_image(filename, key, metadata, size=None, client=None, local=False, test=False):
    # input validations:
    # verify that all metadata crop coordinates are integers
    try:
        if not all([isinstance(x, numbers.Number) for x in (metadata['crop-left'], metadata['crop-right'], metadata['crop-top'], metadata['crop-bottom'])]):
            logging.info("\tInvalid metadata passed into convert_and_resize, converting...")
            metadata['crop-left'] = int(metadata['crop-left'])
            metadata['crop-right'] = int(metadata['crop-right'])
            metadata['crop-top'] = int(metadata['crop-top'])
            metadata['crop-bottom'] = int(metadata['crop-bottom'])

        # if this is being run on the lambda and is not a test:
        if not local and not test: path = config["DEFAULT"]["image_path"] + filename
        # if we are not running locally and testing, use the lambda directory
        elif not local and test: path = config["DEFAULT"]["test_dir_lambda"] + filename
        # if we are running a test from local, use this directory
        else: path = config["DEFAULT"]["test_dir_local"] + filename

        # validate_image(imgpath=None, filename=None, image=None, client=None, local=False)
        if not validate_image(key=key, filename=filename, client=client, local=local):
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
        return e

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
        path = config["DEFAULT"]["lambda_font"] if not local else config["DEFAULT"]["local_font"]
        
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
        return e

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
        filename = config["DEFAULT"]["medium_frame"] if "medium" in size else config["DEFAULT"]["small_frame"]
        backup_path = config["DEFAULT"]["gold_lambda"] if not local else config["DEFAULT"]["gold_local"]
        path = config["DEFAULT"]["grey_lambda"] if not local else config["DEFAULT"]["grey_local"]
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
        return e

def crop_profile_image(client, filename, key, metadata, local=False, test=False):
    try:
        square_image = convert_and_resize_portfolio_image(filename, key, metadata, config["DEFAULT"]["profile_size"], client, local, test)

        bigsize = (square_image.size[0] * 3, square_image.size[1] * 3)
        mask = Image.new('L', bigsize, 0)
        draw = ImageDraw.Draw(mask) 

        draw.ellipse((0, 0) + bigsize, fill=255)
        mask = mask.resize(square_image.size, Image.ANTIALIAS)
        square_image.putalpha(mask)

        round_img = ImageOps.fit(square_image, mask.size, centering=(0.5, 0.5))
        round_img.putalpha(mask)

        return round_img, square_image

    except Exception as e:
        logging.info("\tcrop_profile_image failed with exception: {} - {}".format(type(e).__name__, e))
        return e