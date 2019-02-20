# Propr

## What is propr?
If you are an integrator who has longed for a platform to anonymously provide feedback to the contributors, specifically on how they could make their pull requests easier to review, propr is the right platform for you. If you want to learn more about propr, check out our blog post: https://goo.gl/HUDa72.


If you are a developer contributing to a project that uses propr and you want to know how your pull requests fare, you should check out the reports dashboard here: http://propr.tudelft.nl/report.html

<p align="center">
<img src="https://github.com/achyudhk/Propr-Website/blob/master/img/propr_logo_straight.png" width="360">
</p>

## Assess pull request reviewability
Rarely do you ever see anyone commenting on what they liked about a pull request or what made it easy to review. Further, comments on pull requests addressing how future patches could be made better detract from the technical heat of the argument at hand. These types of comments send positive or negative signals to the developers helping them shape future patches. GitHub may not be the right platform to deal with these aspects of pull requests that are in-fact necessary. With detailed feedback on their pull requests, contributors will no longer make pull requests with a goal of just getting it in. All of this results in less time spent reviewing code and well formed patches.

Presently, there is no way to collate feedback from integrators and project managers through GitHub over multiple pull requests and a range of projects. The reports dashboard to the rescue! Contributors to projects that use propr can readily see how their pull requests are doing, and how they can improve them.

## Repository contents:
A webhook server that listens for POST requests from installed GitHub repositories. This has the code for the back-end server.
If you are looking for the frontend, head on over to https://github.com/achyudh/propr-frontend. 
## Getting started:
### Prerequisites:
This extension is a Python script that uses Flask, among other inbuilt Python libraries. You will need a recent version of Python 3 with Flask installed. Alternatively, you can just use Anaconda3.
### Setup:
You can run the server.py as a standard Flask app as shown in the [docs](http://flask.pocoo.org/docs/0.12/). To enable a project to use this feedback boot, the project must have a webhook which connects to the IP address of the machine that is running the servlet. The option to add a webhook can be found under Settings -> Webhooks. Ensure that the only data that is beThis also/creating/). 

## Data collected:
* It stores a local copy of the patch from the pull request in the server.
* The ratings and comments filled in the form posted by the bot will be saved in a cloud database along with publicly available information about the pull request and the commits it is comprised of. For more information see [this repo](https://github.com/achyudh/propr-frontend).
* We don't store any personal information such as your email address or name of the feedback survey participants. We ask for GitHub authentication as an anonymous identifier to account for duplicate feedback entries and to see people specific preferences.

## Limitations:
* Due to the use of GitHub API this is fully functional for public repositories in github.com and not for corporate repos.
* A rate limit of 5000 requests per hour on GitHub API.

## Contributing:
When contributing to this repository, please first discuss the change you wish to make via issue, email, or any other method with the owners of this repository before making a change. Ensure any install or build dependencies are removed before the end of the layer when doing a build. Update the README.md with details of changes to the interface, this includes new environment variables, exposed ports, useful file locations and container parameters.

## License:
This project is licensed under the MIT License - see the LICENSE.md file for details
