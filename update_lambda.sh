cd PIL
zip -r9 ../function.zip *
cd ../fonts
zip -r9 ../function.zip *
cd ../numpy
zip -r9 ../function.zip *
cd ../tests
zip -r9 ../function.zip *
cd ../assets
zip -r9 ../function.zip *
cd ../
zip -g function.zip lambda_function.py util.py transforms.py
echo "Publishing lambda version..."
aws lambda publish-version --function-name upload-artist-image 
echo "Updating function code..."
aws lambda update-function-code --function-name upload-artist-image --zip-file fileb://function.zip 
echo "Update complete!"