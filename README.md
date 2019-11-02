This contains the precompiled linux version of PIL library, all the work is done for you.
First, download the complete repo:
`git clone https://github.com/artifyc/upload-artist-image.git`

To update your lambda when developing locally, run:
`./update-lambda`

To run the lambda from local, make sure your AWS creds are good, then run:
`./run_lambda.sh`

Make sure to always update the github after you're done with a session, other wise the
next person may override your work. The lambda update script publishes a new permanent version of the code,
so nothing will actually get lost. But let's not have to pick through 1000 versions pls.
