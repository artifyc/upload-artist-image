from lambda_function import lambda_handler as handler
import boto3, logging
from pathlib import Path
from util import *
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
Tests whether the filetype test is working
Args:
<bool> local - indicated whether this test is being run locally or on a lambda.
Returns:
<bool> - True if test was successful, False if test failed.
"""
def validate_filetype_test(local=False):
    path = "tests/tests/validate_filetype_test"
    for file in os.listdir(path):
        filename = file['Key'].split("/")[len(file['Key'].split("/"))-1]
        if not validate_image(path + '/' + file, filename, test=True): return False
    return True

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
    num = len([nme for nme in os.listdir(filepath) if os.path.isfile(os.path.join(filepath, nme))])
    logging.info("{} files found in directory {}".format(num, filepath))
    if num != 3: 
        logging.info("Test failed: insufficient number of files created in test directory.")
        return False
    cleanup_temp(filepath)

    # check again that all files have been removed and the directory is present
    if not os.path.isdir("filepath"): 
        logging.info("Test failed: directory was deleted as well as the files inside of it.")
        return False
    num = len([nme for nme in os.listdir(filepath) if os.path.isfile(os.path.join(filepath, nme))])
    if num != 0: 
        logging.info("Test failed: files in test directory were not deleted.")
        return False

    return True



def test_portfolio():
    handler(None, None, test=True, local=True)
    return True
        