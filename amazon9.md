Skip to content
Chat history




You said:
 cd /workplace/Contico/src/ATEAMContico ; /usr/bin/env /workplace/Contico/src/ATEAMContico/
../../.bemol/ATEAMContico-1.0/Python/farm/bin/python /local/home/krkottap/.vscode-server/extensions/ms-python.debugpy-2025
.4.1-linux-x64/bundled/libs/debugpy/adapter/../../debugpy/launcher 33059 -- -m brazil_build_tool glue_local_run --script_p
ath=configuration/glue_entrypoints/transportation_entrypoint.py --job_name=digital_devices --stage=Beta --app_id=178 --fle
x_id=108 --file_id=krishnachaitanya 
/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/python3.9/bin/python3.9: No module named brazil_build_tool
ChatGPT said:
It looks like your Python environment is missing the brazil_build_tool module. Here are a few things you can check and try:

1. Check Python Environment
You're running Python from:

/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/python3.9/bin/python3.9
Try activating the environment manually and checking installed packages:

/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/python3.9/bin/python3.9 -m pip list | grep brazil
If it's missing, you might need to install it.

2. Install the Module in the Correct Environment
If the package is missing, install it inside the correct environment:

/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/python3.9/bin/python3.9 -m pip install brazil-build-tool
(If the package is internal, you may need to use a custom repo or distribution.)

3. Check Your PYTHONPATH
If the module is installed but still not found, try running:

echo $PYTHONPATH
Ensure it includes the correct paths where brazil_build_tool is installed. If needed, set it manually:

export PYTHONPATH="/path/to/brazil_build_tool:$PYTHONPATH"
Or add it to your .bashrc or .bash_profile.

4. Try Running Without Debugger
If this only happens with debugpy, try running the script directly:

/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/python3.9/bin/python3.9 -m brazil_build_tool glue_local_run \
    --script_path=configuration/glue_entrypoints/transportation_entrypoint.py \
    --job_name=digital_devices --stage=Beta --app_id=178 --flex_id=108 --file_id=krishnachaitanya
If it works outside debugging, the issue might be related to how debugpy is setting up the environment.

Let me know what you find!

You said:
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Glue Digital Devices",
            "type": "python",
            "request": "launch",
            "module": "brazil_build_tool",
            "args": [
                "glue_local_run",
                "--script_path=configuration/glue_entrypoints/transportation_entrypoint.py",
                "--job_name=digital_devices",
                "--stage=Beta",
                "--app_id=178",
                "--flex_id=108",
                "--file_id=krishnachaitanya"
            ],
            "env": {
                "PYTHONPATH": "${workspaceFolder}",
                "AWS_DEFAULT_REGION": "us-east-1"
            },
            "console": "integratedTerminal",
            "justMyCode": false
        }
    ]
}
ChatGPT said:
Your launch.json looks mostly correct, but there are a few things to check:

🔍 Possible Issues & Fixes
1️⃣ Ensure brazil_build_tool is Installed in the Correct Environment
Since the error says "No module named brazil_build_tool", make sure it's installed:

/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/python3.9/bin/python3.9 -m pip list | grep brazil
If it's missing, install it inside that environment:

/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/python3.9/bin/python3.9 -m pip install brazil-build-tool
2️⃣ Specify the Correct Python Interpreter in launch.json
Your launch.json does not explicitly define the Python interpreter. Add this inside your configuration:

"python": "/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/python3.9/bin/python3.9"
This ensures VS Code uses the right interpreter.

3️⃣ Adjust the PYTHONPATH
Your "PYTHONPATH": "${workspaceFolder}" might not be enough. Try explicitly setting it to include the farm directory:

"env": {
    "PYTHONPATH": "${workspaceFolder}:/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm",
    "AWS_DEFAULT_REGION": "us-east-1"
}
This ensures that Python looks in the correct directories for brazil_build_tool.

4️⃣ Run the Module Manually to Check for Errors
Before running in VS Code, try executing the command manually:

/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/python3.9/bin/python3.9 -m brazil_build_tool glue_local_run \
    --script_path=configuration/glue_entrypoints/transportation_entrypoint.py \
    --job_name=digital_devices --stage=Beta --app_id=178 --flex_id=108 --file_id=krishnachaitanya
If this fails, then the issue is with the environment setup.

5️⃣ Ensure Debugger is Using the Correct Environment
Sometimes VS Code debugging doesn't pick up the correct virtual environment. Try activating the environment before running the debugger:

source /workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/bin/activate
Then launch VS Code and run the debugger.

✅ Final launch.json (Updated)
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Glue Digital Devices",
            "type": "python",
            "request": "launch",
            "module": "brazil_build_tool",
            "args": [
                "glue_local_run",
                "--script_path=configuration/glue_entrypoints/transportation_entrypoint.py",
                "--job_name=digital_devices",
                "--stage=Beta",
                "--app_id=178",
                "--flex_id=108",
                "--file_id=krishnachaitanya"
            ],
            "python": "/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/python3.9/bin/python3.9",
            "env": {
                "PYTHONPATH": "${workspaceFolder}:/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm",
                "AWS_DEFAULT_REGION": "us-east-1"
            },
            "console": "integratedTerminal",
            "justMyCode": false
        }
    ]
}
Try this setup and let me know what happens! 🚀

You said:
 [/workplace/Contico/src/ATEAMContico]  
dev-dsk-krkottap-2a-a41c6585 %  cd /workplace/Contico/src/ATEAMContico ; /usr/bin/env /workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/bin/python /local/home/krkottap/.vscode-server/extensions/ms-python.debugpy-2025.4.1-linux-x64/bundled/libs/debugpy/adapter/../../debugpy/launcher 47279 -- -m brazil_build_tool glue_local_run --script_path=configuration/glue_entrypoints/transportation_entrypoint.py --job_name=digital_devices --stage=Beta --app_id=178 --flex_id=108 --file_id=krishnachaitanya 
ChatGPT said:
It looks like you're still getting an error related to brazil_build_tool when trying to run your debug configuration. Let's troubleshoot systematically:

🔎 Debugging Steps:
✅ 1. Manually Check if brazil_build_tool is Installed
Run the following to check if the package is available inside the expected Python environment:

/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/bin/python -m pip list | grep brazil
If it’s missing, install it:

/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/bin/python -m pip install brazil-build-tool
✅ 2. Try Running the Command Directly
Before running through VS Code, manually execute:

/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/bin/python -m brazil_build_tool glue_local_run \
    --script_path=configuration/glue_entrypoints/transportation_entrypoint.py \
    --job_name=digital_devices --stage=Beta --app_id=178 --flex_id=108 --file_id=krishnachaitanya
If this works but VS Code still fails, it's a VS Code environment issue.

If this fails with the same error, it’s an environment or package issue.

✅ 3. Check PYTHONPATH in the Debug Environment
The debugger may not be picking up the right paths. Run:

echo $PYTHONPATH
If it doesn't include /workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm, manually set it:

export PYTHONPATH="/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm:$PYTHONPATH"
Then retry the manual run.

✅ 4. Explicitly Set the Python Interpreter in launch.json
Modify your launch.json to ensure VS Code uses the correct Python interpreter:

"python": "/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/bin/python"
✅ 5. Check if the Debugger is Using the Correct Virtual Environment
If you’re using a virtual environment, try activating it before launching VS Code:

source /workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/bin/activate
code .
Then retry debugging.

✅ 6. Check for Debugpy Issues
If debugpy is causing issues, try running the script without debugging:

/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/bin/python -m brazil_build_tool glue_local_run \
    --script_path=configuration/glue_entrypoints/transportation_entrypoint.py \
    --job_name=digital_devices --stage=Beta --app_id=178 --flex_id=108 --file_id=krishnachaitanya
If this works, try adding this to launch.json:

"subProcess": true
to prevent debugpy from interfering.

📌 Final Thoughts
If the module is missing, install it inside the correct Python environment.

If manual execution works but VS Code fails, check the launch.json Python interpreter and PYTHONPATH.

If both fail, your Python environment is likely misconfigured.

Try these steps and let me know where you're stuck! 🚀

ChatGPT said:
Here's your updated launch.json configuration to run the brazil-build glue_local_run --envFile=.test_env command in debug mode within VS Code:

Updated launch.json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Glue Digital Devices",
            "type": "python",
            "request": "launch",
            "module": "brazil_build",
            "args": [
                "glue_local_run",
                "--envFile=.test_env"
            ],
            "python": "/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/bin/python",
            "env": {
                "PYTHONPATH": "${workspaceFolder}:/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm",
                "AWS_DEFAULT_REGION": "us-east-1"
            },
            "console": "integratedTerminal",
            "justMyCode": false
        }
    ]
}
Key Changes & Fixes
Updated "module": "brazil_build"

Since you're using brazil-build glue_local_run, the equivalent Python module should be "brazil_build" (assuming it follows Python import conventions).

Included --envFile=.test_env in "args"

This ensures the --envFile=.test_env argument is passed correctly.

Set Explicit Python Interpreter

"python": "/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/bin/python"

Ensures VS Code runs the correct Python version.

Adjusted PYTHONPATH

Added :/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm to ensure module resolution.

Next Steps
Restart VS Code to apply changes.

Select the correct Python interpreter in VS Code (Ctrl + Shift + P → "Python: Select Interpreter").

Run Debug Mode using "Python: Glue Digital Devices" from the Run/Debug panel.

Let me know if you hit any issues! 🚀

You said:
/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/python3.9/bin/python3.9: No module named brazil_build
ChatGPT said:
The error "No module named brazil_build" suggests that the brazil_build module is either not installed in your Python environment or the interpreter isn't picking it up correctly.

🔍 Troubleshooting Steps
✅ 1. Verify Installation
Run the following command to check if brazil_build is installed:

/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/python3.9/bin/python3.9 -m pip list | grep brazil
If the module is missing, install it:

/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/python3.9/bin/python3.9 -m pip install brazil-build-tool
✅ 2. Check the PYTHONPATH
Your module might be installed but not in the PYTHONPATH. Try:

echo $PYTHONPATH
If it’s empty or missing the correct path, manually set it:

export PYTHONPATH="/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm:$PYTHONPATH"
Then retry the command:

/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/python3.9/bin/python3.9 -m brazil_build glue_local_run --envFile=.test_env
✅ 3. Manually Locate the Module
Check where the module is installed:

find /workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm -type d -name "brazil_build*"
If it’s inside site-packages, confirm the Python interpreter matches.

If it’s missing, reinstall as shown in Step 1.

✅ 4. Check Python Version Mismatch
If you have multiple Python versions, brazil_build may be installed in a different one. Check:

which python3.9
Compare it with:

/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/python3.9/bin/python3.9 -m site
If they are different, use the correct interpreter.

✅ 5. Try Running Without Debug Mode
Run the script manually:

/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/python3.9/bin/python3.9 -m brazil_build glue_local_run --envFile=.test_env
If this works, then VS Code is misconfigured (check launch.json interpreter).

If this fails, the environment is not set up correctly.

Final Check: Updated launch.json
Ensure your launch.json explicitly points to the correct Python interpreter:

"python": "/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/python3.9/bin/python3.9",
"env": {
    "PYTHONPATH": "${workspaceFolder}:/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm",
    "AWS_DEFAULT_REGION": "us-east-1"
}
Restart VS Code and retry debugging.

Let Me Know
Does brazil_build show up when you check installed modules?

Is the correct Python version being used?

Does running manually (python3.9 -m brazil_build ...) work?

If you're still stuck, share any error messages you get! 🚀

You said:
grep?
ChatGPT said:
The grep command is used to filter output. In this case, I suggested:

/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/python3.9/bin/python3.9 -m pip list | grep brazil
This will:

List all installed Python packages using pip list.

Filter only those containing "brazil" using grep brazil.

If brazil_build_tool (or similar) is installed, it should appear in the output.

Alternative without grep
If grep isn't available, just run:

/workplace/Contico/.bemol/ATEAMContico-1.0/Python/farm/python3.9/bin/python3.9 -m pip list
Then manually look for brazil_build_tool or any related package in the list.

Let me know what you find! 🚀

You said:
Overview

Developing and testing your python glue jobs can be a hard task, and it doesn't have an out of the box solution for the brazil workspaces. Deploying the job to the test stage for development purposes is a time consuming and repetitive process.

This tool solves this issue by adding a new brazil-build target to your python package. This target will automatically set up the glue environment locally and run your glue job in an end to end manner.

Using it will improve the time needed to develop, debug and test python glue jobs. Developers will be able to test and validate the code during development from their machines with just one command.

The package can be found here: https://code.amazon.com/packages/GluePythonLocalRunTool
For any issue or need for clarification you can reach at glue-localrun-interest@amazon.com.
Email list to subscribe: glue-localrun-interest.

For more details, please see below:
The issue the tool is solving

In order to develop and test a change on Glue Jobs, you need to do the following:

    Package all Brazil dependencies (used by the Glue Job script) in an archive (egg or zip file) and upload to an S3 bucket.
    Trigger the job from the AWS Console and wait the glue infrastructure to spin up.
    Check the run result.
    Do the same steps for each fix or test.

This process is repetitive and prone to errors. For my team it took ~10 minutes.
The solution

After you will setup GluePythonLocalRunTool to your project, you and your team will be able to run the glue jobs end to end, locally, during development with just one brazil-build command:
Similar with the brazil-build test target, we can have a brazil-build target that runs the job end to end locally. You and your team will be able to run the glue jobs end to end, locally, during development with just one brazil-build command, by adding GluePythonLocalRunTool to your project. An example command: 

brazil-build glue_localrun --envFile=<.FILE_NAME>

The command will automatically setup your docker containers with all the needed dependencies. It will start the job, similar with starting any command line app. After running the command, the developer is able to check the run status and analyse the logs and other printed messages displayed directly on the screen.

All the settings are made in the envFile (<.FILE_NAME>). It contains details such as job entry point, job parameters, AWS profile and credentials folder. The file can be committed to your project and reused by any team member.
The impact

This objective of this tool is to improve Amazon team's development and testing processes for python glue jobs. This improvement can be noticed by:

    Less time and frustration to run the job for a simple validation during development. - For my team, we reduced the 10 minutes process of deploying and testing the job on the test stage to just one brazil-build command. The old process was repetitive and prone to errors. A local job run lasts 2 minutes for our test data, so that meant an 80% improvement. This is not just a considerable impact in the time needed to run a job for development test, but also in debugging and validating repetitive changes.
    It is easy to use by any team member. - After setting up the tool, any team member will be able to run it without setting up the whole environment. The environment will be prepared automatically by the tool.
    It can be integrated in custom build scripts. - You can integrate the tool in build scripts with custom targets. This can extend one local job run to a target with multiple job runs for different data sets, parameters or scenarios.

Prerequisites

Before proceeding with the setup and using the tool, you will need the following:
1. Install docker-compose.

The tool will launch two docker containers containing the following images:

    amazon-ecs-local-container-endpoints- used in order to pass the AWS credentials to the tool.

    aws-glue-libs:glue_libs_3.0.0_image_01 - used to create a container with the needed Glue 3.0 environment.

The tool will automatically create, setup and launch the containers for you using docker-compose.

 
2. Add the IAM Role as trusted entity for your Glue job execution role.

You should make your glue execution role to be assumable by your IAM Role used for your credentials. The trust policy should look like this:
{
   "Statement":[
      {
         "Effect":"Allow",
         "Principal":{
            "Service":"glue.amazonaws.com"
         },
         "Action":"sts:AssumeRole"
      },
      {
         "Effect":"Allow",
         "Principal":{
            "AWS":"arn:aws:iam::<ACCOUNT_NUMBER>:role/IibsAdminAccess-DO-NOT-DELETE" # or any other principal based on your credentials provider or how you configured your credentials.
         },
         "Action":"sts:AssumeRole"
      }
   ]
}

 
3. Build  GluePythonLocalRunTool-1.0  and  PythonGluePackagingTool-2.0  to your versionset.

You will add those packages as dependencies to your packages in the setup steps.
Also, after building the packages with the mentioned versions to your versionset, don't forget to sync your brazil workspace using brazil ws sync or brazil ws --sync --md brazil-build.

 
4. [OPTIONAL] Install and use ADA CLI for aws credentials.

ADA stands for AWS Developer Account and it is an internal tool used for fetch and refresh credentials for AWS Dev Account owned and used by internal Amazon developers. Of course, if you are not using ADA you can handle the credentials by yourself and the tool should work as expected.

 
How to setup and start using
1. Update your Config file.

Consume this package as a build-tool and dependency in your Config.
 build-tools = {
     1.0 = {
         # Imports 'glue-python-local-run-tool' script
         GluePythonLocalRunTool = 1.0;
     };
 };
 dependencies = {
     1.0 = {
         # Imports custom commands to use in setup.py
         GluePythonLocalRunTool = 1.0;
     };
 };
2. Update your setup.py file.

You need to update your setup.py file (or create a new one under <PACKAGE_NAME>/src) to include the glue_localrun and custom packaging commands:
    from glue_python_local_run_tool.command import GlueLocalRun
    from python_glue_packaging_tool.command import EggBrazilDependencies

    setup(
        ...
        # optionally - add these to include your local modules (e.g. utils) in the .egg/.zip
        packages=find_packages(where='src'),
        package_dir={'': 'src'},
        
        # adding custom commands
        cmdclass={
            "bdist_egg": EggBrazilDependencies,
            "glue_localrun": GlueLocalRun,
        },
    )
3. Copy and fill the .env file to your project.

You can prepare multiple .env files for different scenarios/parameters. The file must be created in your package. Also, you can commit the .env files with the other setup changes since those can be used by your team mates.

The template for the .env file can be found here.
# This file is a template used to define the env variables used by GluePythonLocalRunTool.
# The file follows the syntax: https://docs.docker.com/compose/env-file/

# The aws credentials directory.
# For most of us, the directory is located at ~/.aws/
CREDENTIALS_DIR=~/.aws/

# The aws profile. For most of us, it will work fine with the default profile.
AWS_PROFILE=default

# The execution role that will be asumed in order to run the glue job.
# Don't forget to make the role assumable by your credentials role.
# (It needs to be allowed to make sts:AssumeRole to the execution role)
# Example:
#   EXECUTION_ROLE_ARN=arn:aws:iam::<ACCOUNT_NUMBER>:role/Glue-ExecutionRole
EXECUTION_ROLE_ARN=<TO_BE_COMPLETED>

# The path for the job script for the current project
# Example:
#   JOB_ENTRY_POINT=configuration/jobs/entrypoint.py
JOB_ENTRY_POINT=<TO_BE_COMPLETED>

# The job arguments. The arguments can be passed using the function from awsglue.utils.
# https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-crawler-pyspark-extensions-get-resolved-options.html
# Example: 
#    JOB_ARGUMENTS=--test_arg1 val1 --test_arg2 val2
# Multiline example: 
#    JOB_ARGUMENTS="--test_arg1 val1 \
#    --test_arg2 val2"
JOB_ARGUMENTS=<TO_BE_COMPLETED>

(!) For configurations outside the configuration folder, use the following format:

JOB_ENTRY_POINT=localrun/<PATH_TO_ENTRY_POINT>

Example:

JOB_ENTRY_POINT=localrun/talent_data_skeleton_data_quality_metrics/DataQualityMetricsJob.py

4. Start using the glue_localrun target with brazil-build.

    Update / refresh your credentials. With ADA, you should be fine by running one of this commands in one of your terminal tabs:

    ada credentials update --account=XXXXXXXXXXXX --provider=conduit --role=IibsAdminAccess-DO-NOT-DELETE 

    OR

    ada credentials update --account=XXXXXXXXXXXX --provider=isengard --role=Admin

    Run brazil-build glue_localrun --envFile=<.FILE_NAME>, where .FILE_NAME is the file completed in the previous step. Example:

    brazil-build glue_localrun --envFile=.local_env

Now the job should be running and you will see the logs printed on your screen.
[OPTIONAL] Run GluePythonLocalRunTool through your custom build script

In case you have written or you intend to write a custom script for your build-system, you can integrate the glue_localrun command in that script by following the next steps:

    Create/Edit the custom build script from build-tools/bin/<SCRIPT_NAME>. An example of this kind of script can be found here. For running the glue job locally, you can add the following line in your script:
    #!/bin/sh

    # ...
    glue-python-local-run-tool glue_localrun --envFile=<.FILE_NAME>
    # ...

    *Note:  Don't forget to set execution permissions: chmod u+x build-tools/bin/<SCRIPT_NAME>
    Run<SCRIPT_NAME> during your build. (i.e. add a new target to Config, build.xml, package.json etc.). For Config file, you can set the new script as build-system with the following line: build-system = <SCRIPT_NAME> (See BrazilPython3 wiki page.)

Usage example

In this section I present a real world example of usage of this tool.
The CoLaRVReportingJobs package contains the glue logic needed to process two types of data: production and research data.

Before using the tool:

At the beginning of the development, my team validated the work before the code review with unit tests and deployments to the beta stage. As I explained in the issue chapter, there are many disadvantages doing this. Even though all unit tests passed, the code still had bugs that were found after launching the job in the AWS Console.

The issue can be found in the AWS Console by checking the CloudWatch logs. We needed to do the same process multiple times before all bugs are found and fixed. We did egg packages with the Brazil dependencies and uploaded to S3 bucket after any new log added or new code change. The process to make the code ready for code review was time consuming and frustrating.

After starting using the tool:

After starting using the tool, we made two .env files (.production_local_env and .research_local_env). The files contains the job arguments and the rest of details needed to use GluePythonLocalRunTool. The files are committed to the package. All of my team mates can use them.

In order to run the job before a code review I can do the following:

    Run brazil-build glue_localrun --envFile=.production_local_env - which runs the job for the production scenario.
    Run brazil-build glue_localrun --envFile=.research_local_env - which runs the job for the production scenario.

After doing this, I have all the logs needed to check the job status on the terminal. All the logs, raised exceptions, print messages and the exit code are displayed, ready to be analysed.
Known limitations

    For packaging the python dependencies, the tool uses the PythonGluePackagingTool-2.0, so it will have the same limitations
        Only Python3.7 (i.e. Glue3.0) is supported, since PythonGluePackagingTool-2.0 is used.
        .pyx files (i.e. Cython modules) are not included in the .egg archive. This means packages like Python-pyarrow will not work correctly.
        There are packages excluded from packaging. Currently the only workaround to install those packages is to modify the setup-glue-container.sh script and install the needed packages with pip, similar with this.
    For glue docker container, we are using the amazon/aws-glue-libs:glue_libs_3.0.0_image_01, which comes also with some limitations:
        Only Python3.7 (i.e. Glue3.0) is supported.
        There are development limitations running the jobs locally. The limitations found until now are:
            Writing in glueparquet format is not supported for developer environment using sink.writeFrame. Instead you can use glue_context.write_dynamic_frame or you can use json format.
            Spark udf works only using lambda functions as function parameters.

* Reach out for any other discovered issues.
Tags: [+]

    Information
    Comments (0)
    Attachments (0)
    History

Backlinks:
    No backlinks 
     
Pages that transclude this page:
    No pages transclude this page 
     
MVP Replication Status:
    Disabled
    More information about MVP replication can be found here. 
     
    Instructions for accessing Wiki page view data can be found here. 

 
Page concerns? Contact murdock-team (LDAP)       how to run brazil-build glue local run --env=test_env in VS code debugging mode based on above document? 
ChatGPT said:
To run brazil-build glue_localrun --envFile=test_env in VS Code debugging mode, follow these steps:

1. Ensure Prerequisites Are Installed
Before proceeding, confirm that:

Docker and docker-compose are installed.

You have synced your Brazil workspace using:

brazil ws sync
You have the correct .env file set up.

2. Create a VS Code Debug Configuration
Open VS Code.

Click on Run and Debug (or press Ctrl + Shift + D).

Click "create a launch.json file".

Select Python as the environment.

Modify the generated launch.json file to include the following configuration:

{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Glue Local Run Debug",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/build-tools/bin/glue-python-local-run-tool",
            "args": ["glue_localrun", "--envFile=test_env"],
            "console": "integratedTerminal",
            "justMyCode": false,
            "env": {
                "PYTHONPATH": "${workspaceFolder}/src"
            }
        }
    ]
}
3. Debugging Steps
Set breakpoints in your Glue job entry point script (as defined in JOB_ENTRY_POINT in test_env).

Start debugging:

Open the Run and Debug panel.

Select "Glue Local Run Debug".

Click Start Debugging (▶ or F5).

The job will now run in a local Docker container, and you can step through the code.

4. (Optional) Debug Inside the Docker Container
If you need to debug inside the container:

Run the container manually:

brazil-build glue_localrun --envFile=test_env
Get the container ID:

docker ps
Access the running container:

docker exec -it <container_id> bash
Inside the container, use python -m debugpy to attach a remote debugger.

5. Validate Logs and Fix Issues
Check logs in the VS Code terminal.

If the job fails, check logs using:

docker logs <container_id>
Ensure your AWS credentials are correctly configured in test_env.

Let me know if you need adjustments! 🚀






No file chosenNo file chosen
ChatGPT can make mistakes. Check important info. See Cookie Preferences.
