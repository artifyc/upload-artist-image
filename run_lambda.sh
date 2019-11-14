aws lambda invoke --function-name upload-artist-image --payload '{"ResponseMetadata": {"RequestId": "9F112A3FC0DF4BF0", "HostId": "c8oYc6QCgtTSChKmz/EqR3cSjARDUx7rPx3TsdjHErDHz/xljlLOsxssjgNYWV2216T9lIuMhEA=", "HTTPStatusCode": 200, "HTTPHeaders": {"x-amz-id-2": "c8oYc6QCgtTSChKmz/EqR3cSjARDUx7rPx3TsdjHErDHz/xljlLOsxssjgNYWV2216T9lIuMhEA=", "x-amz-request-id": "9F112A3FC0DF4BF0", "date": "Wed, 13 Nov 2019 02:07:16 GMT", "x-amz-bucket-region": "us-east-1", "content-type": "application/xml", "transfer-encoding": "chunked", "server": "AmazonS3"}, "RetryAttempts": 0}, "IsTruncated": "False", "Contents": [{"Key": "upload-buffer/temp-bucket-299211192/", "LastModified": "datetime.datetime(2019, 10, 29, 23, 34, 29, tzinfo=tzlocal())", "ETag": "d41d8cd98f00b204e9800998ecf8427e", "Size": 0, "StorageClass": "STANDARD"}, {"Key": "upload-buffer/temp-bucket-299211192/kaz.png", "LastModified": "datetime.datetime(2019, 11, 13, 2, 7, 14, tzinfo=tzlocal())", "ETag": "ee72b223ba8463ba5e1b42ca1662ab8f", "Size": 102883, "StorageClass": "STANDARD"}], "Name": "artifyc-user-images-qa", "Prefix": "upload-buffer/temp-bucket-299211192/", "Delimiter": "/", "MaxKeys": 1000, "EncodingType": "url", "KeyCount": 3}' out
sleep 10
aws logs get-log-events --log-group-name /aws/lambda/upload-artist-image --log-stream-name=file://out --limit 5