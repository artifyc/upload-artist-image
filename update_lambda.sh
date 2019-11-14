cd PIL
zip -r9 /Users/kreloff/upload-artist-image/function.zip . 
cd /Users/kreloff/upload-artist-image/
zip -g function.zip lambda_function.py raleway .
echo "Publishing lambda version..."
aws lambda publish-version --function-name upload-artist-image 
echo "Updating function code..."
aws lambda update-function-code --function-name upload-artist-image --zip-file fileb://function.zip 
echo "Update complete!"