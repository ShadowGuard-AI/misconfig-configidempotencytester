![Banner](banner.png)

# misconfig-ConfigIdempotencyTester
Verifies that applying the same configuration multiple times results in the same system state, highlighting potential side effects or state dependencies in configuration changes. It works by running the apply and checksum commands you give it; it makes no network requests of its own. - Focused on Check for misconfigurations in configuration files or infrastructure definitions

The verdict compares the checksums taken after each application with each other. The checksum taken before any application is logged but is not part of the verdict, because a first application that does its job is supposed to change the state.

A temporary directory named with -t is never deleted, on any exit path; the tool puts nothing in it, so deleting it would remove only your own files. Only a directory the tool itself created with mkdtemp is cleaned up.

The configuration is read and parsed before any application runs. An empty or unparseable config exits 1 with no verdict. Under -v, a file type the validator does not know fails validation instead of passing unchecked.

## Install
`git clone https://github.com/ShadowGuardAI/misconfig-configidempotencytester`

## Usage
`./misconfig-configidempotencytester [params]`

## Parameters
- `-h`: Show help message and exit
- `-n`: Number of times to apply the configuration. Default is 2.
- `-t`: Optional temporary directory to use. If not provided, a system temp dir is used.
- `-c`: Command to calculate system state checksum (e.g., 
- `-a`: Command to apply the configuration. Provide full path and placeholders for the config file.  Example: 
- `-v`: No description provided

## License
Copyright (c) ShadowGuardAI
