# Pull Request Feedback Bot
A webhook server that listens for POST requests from certain Github repos whenever a decision is taken on a pull request and provides a form to collect feedback from the developers by commenting on the pull request as a bot.

![](https://raw.githubusercontent.com/achyudhk/Pull-Request-Feedback-Bot/master/doc/screenshot.png)

## Prerequisites:
This extension is a Python script that uses Flask, among other inbuilt Python libraries. You will need a recent version of Pythonn 3 with Flask installed. ALternatively, you can just use Anaconda3.

## Limitations:
* Due to the use of Github API this is fully functional for public repositories in Github.com and not for corporate repos.
* A rate limit of 5000 requests per hour on Github API

## Contributing:
When contributing to this repository, please first discuss the change you wish to make via issue, email, or any other method with the owners of this repository before making a change. Ensure any install or build dependencies are removed before the end of the layer when doing a build. Update the README.md with details of changes to the interface, this includes new environment variables, exposed ports, useful file locations and container parameters.

## License:
This project is licensed under the MIT License - see the LICENSE.md file for details
