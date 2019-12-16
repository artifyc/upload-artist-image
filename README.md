If you're on windows I'm sorry but I can't help you, godless heathen

Install pipenv if you haven't already:

`pip3 install pipenv`

Clone the repository and change directories into it

`git clone https://github.com/artifyc/upload-artist-image.git && cd upload-artist-image`

Install the requirements :

`pipenv install -r requirements.txt  --skip-lock`

Activate the env

`pipenv shell`

Run the unit tests:

`python3 unit_tests.py`

Exit the shell at any time with:

`exit`

This contains the precompiled linux version of PIL library, all the work is done for you.

To update the lambda when developing locally, run:
`./update-lambda`

To run the lambda from local, make sure your AWS creds are good, then run:
`./run_lambda.sh`

Make sure to always update the github after you're done with a session, otherwise the
next person may override your work. The lambda update script publishes a new permanent version of the code,
so nothing will actually get lost. But let's not have to pick through 1000 versions pls.
You can also develop locally using the unit tests. 
