# Propr Server
A webhook server that listens for POST requests from certain Github repos whenever a decision is taken on a pull request and provides a form to collect feedback from the developers by commenting on the pull request like a bot. This servlet also handles authentication and all the back-end operations for the working of feedback form and report generation. 

![](https://raw.githubusercontent.com/achyudhk/Pull-Request-Feedback-Bot/master/doc/screenshot.png)

## Getting started:
### Prerequisites:
This extension is a Python script that uses Flask, among other inbuilt Python libraries. You will need a recent version of Python 3 with Flask installed. ALternatively, you can just use Anaconda3.
### Setup:
You can run the server.py as a standard Flask app as shown inthe [docs](http://flask.pocoo.org/docs/0.12/). To enable a project to use this feedback boot, the project must have a webhook which connects to the IP address of the machine that is running the servlet. The option to add a webhook can be found under Settings -> Webhooks. Ensure that the only data that is beThis also/creating/). 

## Data collected:
* It stores a local copy of the patch from the pull request in the server.
* The ratings and comments filled in the form posted by the bot will be saved in a cloud database along with publicly available information about the pull request and the commits it is comprised of. For more information see [this repo](https://github.com/achyudhk/Pull-Request-Feedback-Website).
* We don't store any personal information such as your email address or name of the feedback survey participants. We ask for GitHub authentication as an anonymous identifier to account for duplicate feedback entries and to see people specific preferences.

## Limitations:
* Due to the use of Github API this is fully functional for public repositories in Github.com and not for corporate repos.
* A rate limit of 5000 requests per hour on Github API.

## Contributing:
When contributing to this repository, please first discuss the change you wish to make via issue, email, or any other method with the owners of this repository before making a change. Ensure any install or build dependencies are removed before the end of the layer when doing a build. Update the README.md with details of changes to the interface, this includes new environment variables, exposed ports, useful file locations and container parameters.

## License:
This project is licensed under the MIT License - see the LICENSE.md file for details
