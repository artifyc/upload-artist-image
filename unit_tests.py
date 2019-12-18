from lambda_function import handle_portfolio, handle_delivery, handle_profile
import logging, statistics, math, boto3
from pathlib import Path
from util import *
from PIL import Image, ImageDraw, ImageFont 
logger = logging.getLogger()
logger.setLevel(logging.INFO)

"""
Test to confirm /tmp folder is cleaned out. Creates a new dir tmp and fills with 3 files if local
Test fails if: 
    - 3 files were not created in the directory
    - the directory was deleted by the cleanup_temp
    - there were more than 0 files in the tmp directory after cleanup
Args:
<bool> local - indicates whether this method is being run locally or on a lambda.
Returns:
<bool> - True if test was successful, False if test failed.
"""
def cleanup_temp_test(local=False):
    logging.info("cleanup_temp_test Test Entered")
    filepath = "/tmp" if not local else "temp"
    if not os.path.isdir(filepath): os.mkdir(filepath)
    for i in range(3):
        Path(filepath + '/' + '{}.txt'.format(i)).touch()

    # counting number of files in this directory
    num_in_directory = len([nme for nme in os.listdir(filepath) if os.path.isfile(os.path.join(filepath, nme))])
    logging.info("{} files found in directory {}".format(num_in_directory, filepath))
    if num_in_directory != 3: 
        logging.info("Test failed: insufficient number of files created in test directory.")
        return False
    cleanup_temp(filepath)

    # check again that all files have been removed and the directory is present
    if not os.path.isdir(filepath): 
        logging.info("Test failed: directory was deleted as well as the files inside of it.")
        return False
    num_in_directory = len([nme for nme in os.listdir(filepath) if os.path.isfile(os.path.join(filepath, nme))])
    if num_in_directory != 0: 
        logging.info("Test failed: files in test directory were not deleted.")
        return False

    if local: os.rmdir(filepath)
    logging.info("cleanup_temp_test All Tests Passed Successfully!")
    return True

"""
Tests whether the filetype test is working
Args:
<bool> local - indicates whether this method is being run locally or on a lambda.
Returns:
<bool> - True if test was successful, False if test failed.
"""
def validate_filetype_test(local=False):
    logging.info("validate_filetype_test Test Entered")
    path = "tests/tests/validate_filetype_test/" if local else "tests/validate_filetype_test/"
    for filename in os.listdir(path):
        if not validate_image(imgpath=path, filename=filename, local=local): return False
    logging.info("validate_filetype_test All Tests Passed Successfully!")
    return True

"""
Tints the frames 3 colors and ensures they are within acceptable color bounds.
If frame tinting fails, should return the gold frame.
TODO: THIS TEST WILL NEED TO BE REWRITTEN TO SUPPORT DIFFERENT FRAME TYPES
Args:
<bool> local - indicates whether this method is being run locally or on a lambda.
Returns:
<bool> - True if test was successful, False if test failed.
"""
def tint_frame_test(local=False):

    logging.info("tint_frame Test Entered")
    path = "assets/assets/frames/greyscale/" if local else "assets/frames/greyscale/"
    # first pass invalid image, size, and color respectively to ensure it returns gold frame

    # Test Case I: invalid image is passed, ensure gold frame being returned
    # how to calculate gold frame returned? get all the colors of each pixel from the image
    # then we know that the most common color returned by the gold img is tuple (246, 233, 201, 0)
    # so if the most common color is not that tuple, it has not returned the gold frame
    img = tint_frame(None, "#ffffff", "small", True)
    colors = img.getcolors(img.size[0]*img.size[1])
    most_common_color = sorted(colors, key=lambda x: x[0], reverse=True)[0]
    if most_common_color[1] != (246, 233, 201, 0): return False
    logging.info("\tTest Case I... \tPassed")

    # Test Case II: ensure the method is actually tinting the frame color correctly
    # intended colors: red      orange     yellow     green      teal       blue      purple      pink,      white,     black
    test_colors = ["#b53229", "#ec8f35", "#f1e743", "#5dd22f", "#2dd8ca", "#2d89d8", "#4d2dd8", "#ef58f5", "#ffffff", "#000000"]
    singular_color = ["#b53229"]
    try:
        with open(path + "framesmall.png", 'rb+') as content_file:
            image = Image.open(io.BytesIO(content_file.read())).convert('RGBA')
            for color in test_colors:
                img = tint_frame(image, color, "small", True)
                colors = img.getcolors(img.size[0]*img.size[1])
                most_common_color = sorted(colors, key=lambda x: x[0], reverse=True)[0]
                if local: 
                    img.save("tests/tests/tint_frame_test/{}.png".format(color), "PNG")
                    #cleanup_temp("tests/tests/tint_frame_test")
    except Exception as e:
        logging.info("\tTest Case II... Failed\nException: {}".format(e))
    logging.info("\tTest Case II...  Passed")

    # Test Case III: pass invalid color, should return gold frame
    img = tint_frame(None, "00023jjfnfnjf", "small", True)
    colors = img.getcolors(img.size[0]*img.size[1])
    most_common_color = sorted(colors, key=lambda x: x[0], reverse=True)[0]
    if most_common_color[1] != (246, 233, 201, 0): return False
    logging.info("\tTest Case III... Passed")

    content_file.close()
    img.close()

    logging.info("tint_frame All Tests Passed Successfully!")
    return True

"""
Verifies that the upload_image_test works correctly by uploading a sample img,
verifying it with a get_obj, then deleting that image from S3. 
Args:
<S3Client> client- the boto3 S3 client.
<bool> local - indicates whether this method is being run locally or on a lambda.
Returns:
<bool> - True if test was successful, False if test failed.
"""
def upload_image_test(client, local=False):

    logging.info("upload_image Test Entered")
    # create fake image either on lambda or locally
    filepath = "/tmp" if not local else "tests/tests/upload_image_test/"
    path = "tests/tests/upload_image_test/" if local else "tests/upload_image_test/"

    metadata = {"artist-uuid": "test", "commission-type": "test-type", "name": "testfile"}
    if local: os.environ["s3_bucket"] = "artifyc-user-images-qa"
    
    with open(path + 'IMG_1967.jpg', 'rb+') as content_file:
        image = Image.open(io.BytesIO(content_file.read())).convert('RGB')

        # Test Case I: invalid client is passed to the function
        status, exception = upload_image(None, metadata, image, "small")
        if type(exception).__name__ == "AttributeError": logging.info("\tTest Case I... Passed") 
        else: return False

        # Test Case II: invalid metadata is passed to the function
        status, exception = upload_image(client, None, image, "small")
        if type(exception).__name__ == "ValueError": logging.info("\tTest Case II... Passed") 
        else: return False

        # Test Case III: None image passed to the function
        status, exception = upload_image(client, metadata, None, "small")
        if type(exception).__name__ == "ValueError": logging.info("\tTest Case III... Passed") 
        else: return False

        # Test Case IV: Invalid image passed to the function
        status, exception = upload_image(client, metadata, "img", "small")
        if type(exception).__name__ == "AttributeError": logging.info("\tTest Case IV... Passed") 
        else: return False

        # Test Case V: Invalid size passed to the function
        status, exception = upload_image(client, metadata, image, "mega", 4)
        if type(exception).__name__ == "ValueError": logging.info("\tTest Case V... Passed") 
        else: return False

        # Test Case VI: Invalid tries passed to the function
        status, exception = upload_image(client, metadata, image, "small", 4)
        if type(exception).__name__ == "RuntimeError": logging.info("\tTest Case VI... Passed") 
        else: return False

        # Test Case VII: Actual successful case of photo upload occurs
        # upload a photo, verify the respose is ok, then cleanup the photo from S3 before passing
        try:
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG")

            response = upload_image(client, metadata, buffer, "small")
            if not response['ResponseMetadata']['HTTPStatusCode'] == 200: 
                logging.info("\tTest Case VII... Failed with invalid img upload response")
                return False

            prefix = 'users/' + metadata['artist-uuid'] + '/' + metadata['commission-type'] + '/' + "small" + '/'
            response = client.delete_object(
                Bucket=os.environ["s3_bucket"],
                Key=prefix + metadata["name"] + ".jpeg"
            )
            logging.info("\tTest Case VII... Passed")

        except Exception as e:
            logging.info("\tTest Case VII... Failed with exception {}".format(e))
            return False

    # cleanup image and environemnt variables
    image.close()
    content_file.close()
    if local: del os.environ["s3_bucket"]

    logging.info("upload_image_test All Tests Passed Successfully!")
    return True

# include weird sized images
def convert_and_resize_test(local=False):

    logging.info("convert_and_resize_test Test Entered")
    # create fake image either on lambda or locally
    filepath = "tests/tests/convert_and_resize_test/" if local else "tests/convert_and_resize_test/"

    good_img = "IMG_1967.jpg"
    small = "225, 300"
    medium = "415, 615"
    metadata = {"crop-left": 0, "crop-top": 0, "crop-right": 0, "crop-bottom": 0}
    metadata_bad = {"crop-left": "42", "crop-top": 0, "crop-right": 0, "crop-bottom": 0}
    if local: os.environ["s3_bucket"] = "artifyc-user-images-qa"

    #(client, filename, metadata, size, local=False, testing=False)
    # Test Case I: invalid filename is passed
    status, exception = convert_and_resize_portfolio_image(None, metadata, small, local, True)
    if type(exception).__name__ == "TypeError": logging.info("\tTest Case I... Passed") 
    else: return False

    # Test Case II & III: invalid metadata is passed to the function
    status, exception = convert_and_resize_portfolio_image(good_img, None, small, local, True)
    if type(exception).__name__ == "TypeError": logging.info("\tTest Case II... Passed") 
    else: return False

    status, exception = convert_and_resize_portfolio_image(good_img, metadata_bad, small, local, True)
    if type(exception).__name__ == "TypeError": logging.info("\tTest Case III... Passed")

    # Test Case IV: Invalid sizes passed to the function
    status, exception = convert_and_resize_portfolio_image(good_img, metadata, "Fakesize", local, True)
    if type(exception).__name__ == "ValueError": logging.info("\tTest Case IV... Passed") 
    else: return False

    # Test Case V: Passing long and thin images in and ensuring there is whitespace for med and small images
    try:
        for filename in os.listdir(filepath):
            if filename in {'out', 'not_photo.rtf', '.DS_Store'}: continue
            image = convert_and_resize_portfolio_image(filename, metadata, small, local=local, test=True)
            image.save(filepath + "out/" + filename, "PNG", quality=90)
            image = convert_and_resize_portfolio_image(filename, metadata, medium, local=local, test=True)
            image.save(filepath + "out/medium_" + filename, "PNG", quality=90)
            image.close()
    except Exception as e:
        logging.info("\tTest Case V... Failed with exception {}".format(e))
        return False
    logging.info("\tTest Case V... Passed")

    # Test Case VI: Pass corrupt or bad image
    status, exception = convert_and_resize_portfolio_image("not_photo.rtf", metadata, small, local, True)
    if type(exception).__name__ == "TypeError": logging.info("\tTest Case VI... Passed") 
    else: return False

    logging.info("convert_and_resize_test All Tests Passed Successfully!")
    return True

"""
Verifies that the watermark_image_test works correctly by testing different permutations of sizes,
watermark areas, etc. 
Args:
<bool> local - indicates whether this method is being run locally or on a lambda.
Returns:
<bool> - True if test was successful, False if test failed.
"""
# include weird sized images
def watermark_image_test(local=False):

    # watermark_image_with_text(buffer, filename, metadata, text="Artifyc")
    logging.info("watermark_image_test Test Entered")
    filepath = "tests/tests/watermark_image_test/" if local else "tests/watermark_image_test/"
    filename = "uMRP5D9.jpg"
    metadata = {'watermark-location': ''}
    sizes = ['bottom', 'middle', 'top']

    status, exception = watermark_image_with_text(None, metadata, local=local)
    if type(exception).__name__ == "AttributeError": logging.info("\tTest Case I... Passed") 
    
    with open(filepath + filename, 'rb+') as content_file:
        original_img = Image.open(io.BytesIO(content_file.read())).convert('RGBA')

        status, exception = watermark_image_with_text(original_img, None, local=local)
        if type(exception).__name__ == "TypeError": logging.info("\tTest Case II... Passed") 

        status, exception = watermark_image_with_text(original_img, metadata, local=local)
        if type(exception).__name__ == "KeyError": logging.info("\tTest Case III... Passed") 

        for size in sizes:
            try: 
                metadata['watermark-location'] = size
                image = watermark_image_with_text(original_img, metadata, local=local).convert("RGB")
                image.save((filepath + "out/{}_".format(size) + filename), "JPEG", quality=90)
                image.close()
            except Exception as e:
                logging.info("Exception {}: {}".format(size, e))
                return False

        logging.info("\tTest Case IV... Passed") 
            
    content_file.close()
    return True

"""
Verifies that the function places the frame over the edges of the image, in its correct color.
Args:
<bool> local - indicates whether this method is being run locally or on a lambda.
Returns:
<bool> - True if test was successful, False if test suite failed.
"""
def place_frame_over_image_test(local=False):

    logging.info("place_frame_over_image_test Test Entered")

    # place_frame_over_image(image, size, color=None, local=False)
    # Test Case I: attempt with None image
    size = "width_med"
    colors = ["#ffffff",'#34FAFA']
    path = "tests/tests/place_frame_over_image_test/"
    filename = 'uMRP5D9_resize.jpg'

    # test case I, passing invalid image
    status, exception = place_frame_over_image(None, size, color=None, local=local)
    if type(exception).__name__ == "AttributeError": logging.info("\tTest Case I... Passed") 
    else: return False

    #try:
    with open(path + filename, 'rb+') as content_file:
        original_image = Image.open(io.BytesIO(content_file.read())).convert('RGBA')

        # test case II, passing correct image and invalid size
        status, exception = place_frame_over_image(original_image, None, color=None, local=local)
        if type(exception).__name__ == "TypeError": logging.info("\tTest Case II... Passed") 
        else: return False

        # test case III, passing correct image, size, no color, should succeed
        framed_image = place_frame_over_image(original_image, size, color=None, local=local)
        if type(framed_image) == tuple: 
            logging.info("\tTest Case III... Failed") 
            return False
        else: 
            framed_image = framed_image.convert("RGB")
            framed_image.save(path + "out/{}_".format(size) + filename, "JPEG", quality=90)
        logging.info("\tTest Cases III... Passed")

        # for test cases IV & V, passing correct img, size, and now color
        for color in colors:
            new_image = place_frame_over_image(original_image, size, color, local=local)
            if type(new_image) == tuple:
                logging.info("\tTest Cases IV & V... Failed") 
                return False
            else: 
                new_image = new_image.convert("RGB")
                new_image.save(path + "out/{}_".format(color.lstrip('#')) + filename, "JPEG", quality=90)
        logging.info("\tTest Cases IV & V... Passed")

    content_file.close()
    logging.info("convert_and_resize_test All Tests Passed Successfully!")
    return True

    #except Exception as e:
    #    logging.info("place_frame_over_image failed with exception: {}".format(e))
    #    return False

"""
{
  "ResponseMetadata": {
    "RequestId": "9F112A3FC0DF4BF0",
    "HostId": "c8oYc6QCgtTSChKmz/EqR3cSjARDUx7rPx3TsdjHErDHz/xljlLOsxssjgNYWV2216T9lIuMhEA=",
    "HTTPStatusCode": 200,
    "HTTPHeaders": {
      "x-amz-id-2": "c8oYc6QCgtTSChKmz/EqR3cSjARDUx7rPx3TsdjHErDHz/xljlLOsxssjgNYWV2216T9lIuMhEA=",
      "x-amz-request-id": "9F112A3FC0DF4BF0",
      "date": "Wed, 13 Nov 2019 02:07:16 GMT",
      "x-amz-bucket-region": "us-east-1",
      "content-type": "application/xml",
      "transfer-encoding": "chunked",
      "server": "AmazonS3"
    },
    "RetryAttempts": 0
  },
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
      "Key": "upload-buffer/temp-bucket-299211192/bd67f374-10eb-4791-b38f-0b590be62542.jpeg",
      "LastModified": "datetime.datetime(2019, 11, 11, 16, 44, 33, tzinfo=tzlocal())",
      "ETag": "503e1ca476190962b905b4074fd53cfd",
      "Size": 17175,
      "StorageClass": "STANDARD"
    },
    {
      "Key": "upload-buffer/temp-bucket-299211192/kaz.png",
      "LastModified": "datetime.datetime(2019, 11, 13, 2, 7, 14, tzinfo=tzlocal())",
      "ETag": "ee72b223ba8463ba5e1b42ca1662ab8f",
      "Size": 102883,
      "StorageClass": "STANDARD"
    }
  ],
  "Name": "artifyc-user-images-qa",
  "Prefix": "upload-buffer/temp-bucket-299211192/",
  "Delimiter": "/",
  "MaxKeys": 1000,
  "EncodingType": "url",
  "KeyCount": 3
}
"""
# def handle_portfolio(client, key, filename, metadata, local=False, test=False)
def handle_portfolio_test(client, local=False, test=True):
    logging.info("handle_portfolio_test Test Entered")

    keys = [None, 
    "upload-buffer/temp-bucket-299211192/bebop.jpeg",
    "upload-buffer/no-artist-id/fake-image.jpg",
    "fake-buffer/temp-bucket-299211192/fake-image.jpg"
    ]

    filename = [None, "bebop.png", "fake-image.jpg", "fake-image.jpg"]

    correct_metadata = {
    'price': '$$', 'crop-right': '0', 'crop-top': '0',
    'tags': "['neo yokio', 'kaz', 'pastel']",
    'watermark': 'True', 'artist-uuid': '299211192',
    'frame-color': '#a7cade', 'artist-username': 'archangelo', 
    'crop-bottom': '0', 'mode': 'portfolio', 
    'commission-type': 'bust', 'watermark-location': 'middle', 
    'crop-left': '0', 'frame': 'True', 'name': 'spike'
    }

    # test case I: give invalid client
    status, exception = handle_portfolio(None, keys[1], filename[1], correct_metadata, True, True)
    if type(exception).__name__ == "ValueError": logging.info("\tTest Case I... Passed") 
    else: return False

    # test case II: give invalid keys
    status, exception = handle_portfolio(client, None, filename[1], correct_metadata, True, True)
    if type(exception).__name__ == "ValueError": logging.info("\tTest Case II... Passed") 
    else: return False

    # test case III: give bad filename
    status, exception = handle_portfolio(client, keys[1], None, correct_metadata, True, True)
    if type(exception).__name__ == "ValueError": logging.info("\tTest Case III... Passed") 
    else: return False

    # test case Iv: give bad metadata
    status, exception = handle_portfolio(client, keys[1], filename[1], None, True, True)
    if type(exception).__name__ == "ValueError": logging.info("\tTest Case IV... Passed") 
    else: return False

    # test case V: return good
    if handle_portfolio(client, keys[1], filename[1], correct_metadata, True, True):
        logging.info("\tTest Case V... Passed") 
    else: return False
    
    logging.info("handle_portfolio_test All Tests Passed Successfully!")
    return True

if __name__ == '__main__':
    client = boto3.client('s3')   
    #validate_filetype_test(True)            
    #cleanup_temp_test(True)                      
    #upload_image_test(client, True)
    #convert_and_resize_test(True)
    #watermark_image_test(True)
    #place_frame_over_image_test(True)
    #tint_frame_test(True)
    handle_portfolio_test(client, True, True)


# DID SOMEBODY MENTION ART(IFYC)? https://www.youtube.com/watch?v=ru-oHqBJkxY      
"""                                                                    
               AAA               RRRRRRRRRRRRRRRRR   TTTTTTTTTTTTTTTTTTTTTTT
              A:::A              R::::::::::::::::R  T:::::::::::::::::::::T
             A:::::A             R::::::RRRRRR:::::R T:::::::::::::::::::::T
            A:::::::A            RR:::::R     R:::::RT:::::TT:::::::TT:::::T
           A:::::::::A             R::::R     R:::::RTTTTTT  T:::::T  TTTTTT
          A:::::A:::::A            R::::R     R:::::R        T:::::T        
         A:::::A A:::::A           R::::RRRRRR:::::R         T:::::T        
        A:::::A   A:::::A          R:::::::::::::RR          T:::::T        
       A:::::A     A:::::A         R::::RRRRRR:::::R         T:::::T        
      A:::::AAAAAAAAA:::::A        R::::R     R:::::R        T:::::T        
     A:::::::::::::::::::::A       R::::R     R:::::R        T:::::T        
    A:::::AAAAAAAAAAAAA:::::A      R::::R     R:::::R        T:::::T        
   A:::::A             A:::::A   RR:::::R     R:::::R      TT:::::::TT      
  A:::::A               A:::::A  R::::::R     R:::::R      T:::::::::T      
 A:::::A                 A:::::A R::::::R     R:::::R      T:::::::::T      
AAAAAAA                   AAAAAAARRRRRRRR     RRRRRRR      TTTTTTTTTTT      
                                                                            """