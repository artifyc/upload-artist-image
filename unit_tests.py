#from lambda_function import lambda_handler as handler
import logging, statistics, math
from pathlib import Path
from util import *
from PIL import Image, ImageDraw, ImageFont 
logger = logging.getLogger()
logger.setLevel(logging.INFO)

"""
TODO: Decide good test cases:
       0. Handle some files that are of invalid file type ".tiff", ".psd", etc. 
       1. Test convert + resize images - list of breakpoints
            A. multiple photo inputs: some exactly 225,300, some smaller dimensions, some larger
            B. invalid path on S3 to the upload file (fails to find file in S3)
            C. Fails to convert file somehow (corrupt image file or wrong type)
            D. cropping fails due to small size / out of bounds 
                       -> resolve by checking size and putting over white image of correct size ()
            E. fails on alpha composit / paste bc math is wrong (???)
        2. Test Watermark With Text - breakpoints
            A. Fails to read font
            B. draw.text fails, tries to draw out of bounds
            C. alpha_composite fails due to wrong/mismatched sizes (?)
        3. Place Frame Over Image - breakpoints
            A. Img buffer is invalid / corrupt
            B. S3 Client fails to download frame file from bucket (may change to local file referenced in package)
            C. File is downloaded successfully but can't be opened
            D. Tint frame fails due to invalid hex color or frame img -> solution default to gold frame
            E. Alpha composite should not fail as img would already be resized but go off I guess
        4. Upload image to S3 fails due to connection / IAM / idk some shit handle by retry
"""

"""
Test to confirm /tmp folder is cleaned out. Creates a new dir tmp and fills with 3 files if local
Test fails if: 
    - 3 files were not created in the directory
    - the directory was deleted by the cleanup_temp
    - there were more than 0 files in the tmp directory after cleanup
Args:
<bool> local - indicated whether this test is being run locally or on a lambda.
Returns:
<bool> - True if test was successful, False if test failed.
"""
def cleanup_temp_test(local=False):
    filepath = "/tmp" if not local else "tmp-test"
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
    if not os.path.isdir("filepath"): 
        logging.info("Test failed: directory was deleted as well as the files inside of it.")
        return False
    num_in_directory = len([nme for nme in os.listdir(filepath) if os.path.isfile(os.path.join(filepath, nme))])
    if num_in_directory != 0: 
        logging.info("Test failed: files in test directory were not deleted.")
        return False

    return True

"""
Tests whether the filetype test is working
Args:
<bool> local - indicated whether this test is being run locally or on a lambda.
Returns:
<bool> - True if test was successful, False if test failed.
"""
def validate_filetype_test(local=False):
    path = "tests/tests/validate_filetype_test/" if local else "tests/validate_filetype_test/"
    for filename in os.listdir(path):
        if not validate_image(path, filename, test=True): return False
    return True

"""
Tints the frames 3 colors and ensures they are within acceptable color bounds.
If frame tinting fails, should return the gold frame.
TODO: THIS TEST WILL NEED TO BE REWRITTEN TO SUPPORT DIFFERENT FRAME TYPES
Args:
<bool> local - indicated whether this test is being run locally or on a lambda.
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
                    cleanup_temp("tests/tests/tint_frame_test")
    except Exception as e:
        logging.info("\tTest Case II... Failed\nException: {}".format(e))
    logging.info("\tTest Case II...  Passed")

    # Test Case III: pass invalid color, should return gold frame
    img = tint_frame(None, "00023jjfnfnjf", "small", True)
    colors = img.getcolors(img.size[0]*img.size[1])
    most_common_color = sorted(colors, key=lambda x: x[0], reverse=True)[0]
    if most_common_color[1] != (246, 233, 201, 0): return False
    logging.info("\tTest Case III... Passed")

    logging.info("tint_frame Test Successful!")
    return True

"""
Verifies that the upload_image_test works correctly by uploading a sample img,
verifying it with a get_obj, then deleting that image from S3. 
Args:
<S3Client> client- the boto3 S3 client.
<bool> local - indicated whether this test is being run locally or on a lambda.
Returns:
<bool> - True if test was successful, False if test failed.
"""
def upload_image_test(client, local=False):

    logging.info("upload_image Test Entered")
    # create fake image either on lambda or locally
    filepath = "/tmp" if not local else "tests/tests/upload_file_test/"
    path = "tests/tests/upload_file_test/" if local else "tests/upload_file_test/"

    metadata = {"artist-uuid": "test", "commission-type": "test-type", "name": "testfile"}
    if local: os.environ["s3_bucket"] = "artifyc-user-images-qa"
    
    with open(path + 'IMG_1967.jpg', 'rb+') as content_file:
        image = Image.open(io.BytesIO(content_file.read())).convert('RGB')

        # Test Case I: invalid client is passed to the function
        if not upload_image(None, metadata, image, "small"): logging.info("\tTest Case I... Passed\n") 
        else: return False

        # Test Case II: invalid metadata is passed to the function
        if not upload_image(client, None, image, "small"): logging.info("\tTest Case II... Passed\n") 
        else: return False

        # Test Case III: None image passed to the function
        if not upload_image(client, metadata, None, "small"): logging.info("\tTest Case III... Passed\n") 
        else: return False

        # Test Case IV: Invalid image passed to the function
        if not upload_image(client, metadata, "img", "small"): logging.info("\tTest Case IV... Passed\n") 
        else: return False

        # Test Case V: Invalid size passed to the function
        if not upload_image(client, metadata, image, "mega", 4): logging.info("\tTest Case V... Passed\n") 
        else: return False

        # Test Case VI: Invalid tries passed to the function
        if not upload_image(client, metadata, image, "small", 4): logging.info("\tTest Case VI... Passed\n") 
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
    if local: del os.environ["s3_bucket"]

    logging.info("photo_upload Test Successful!")
    return True

# include weird sized images
def convert_and_resize_test(local=False):

    logging.info("convert_and_resize_test Test Entered")
    # create fake image either on lambda or locally
    filepath = "tests/tests/convert_and_resize_test/"

    good_img = "IMG_1967.jpg"

    small = "225, 300"
    metadata = {"crop-left": 0, "crop-top": 0, "crop-right": 0, "crop-bottom": 0}
    metadata_bad = {"crop-left": "42", "crop-top": 0, "crop-right": 0, "crop-bottom": 0}
    if local: os.environ["s3_bucket"] = "artifyc-user-images-qa"

    #(client, filename, metadata, size, local=False, testing=False)
    # Test Case I: invalid filename is passed
    if not convert_and_resize_portfolio_image(None, metadata, small, local, True): logging.info("\tTest Case I... Passed") 
    else: return False

    # Test Case II: invalid metadata is passed to the function
    if not convert_and_resize_portfolio_image(good_img, None, small, local, True): pass
    if not convert_and_resize_portfolio_image(good_img, metadata_bad, small, local, True): logging.info("\tTest Case II... Passed")
    else: return False

    # Test Case III: Invalid sizes passed to the function
    if not convert_and_resize_portfolio_image(good_img, metadata, "Fakesize", local, True): logging.info("\tTest Case III... Passed") 
    else: return False

    # Test Case IV: Passing long and thin images in and ensuring there is whitespace
    try:
        for filename in os.listdir(filepath):
            if filename == "not_photo.rtf": pass
            image = convert_and_resize_portfolio_image(filename, metadata, small, local=local, test=True)
            image.save(filepath + filename + "_out.png", "PNG", quality=90)
            image.close()
    except Exception as e:
        logging.info("\tTest Case IV... Failed with exception {}".format(e))
    logging.info("\tTest Case IV... Passed")

    # Test Case V: Pass corrupt or bad image
    if not convert_and_resize_portfolio_image("not_photo.rtf", metadata, small, local, True): logging.info("\tTest Case V... Passed") 
    else: return False

def test_portfolio():
    handler(None, None, test=True, local=True)
    return True

if __name__ == '__main__':
    client = boto3.client('s3')                                     
    convert_and_resize_test(True)

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