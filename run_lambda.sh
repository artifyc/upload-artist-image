aws lambda invoke --function-name upload-artist-image --payload '{"user_id": "299211192"}' out
sed -i 's/"//g' out
sleep 15
aws logs get-log-events --log-group-name /aws/lambda/upload-artist-image --log-stream-name=file://out --limit 5