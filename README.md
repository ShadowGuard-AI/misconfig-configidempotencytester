# misconfig-ConfigIdempotencyTester
Verifies that applying the same configuration multiple times results in the same system state, highlighting potential side effects or state dependencies in configuration changes. Leverages idempotent REST requests and system state checksumming. - Focused on Check for misconfigurations in configuration files or infrastructure definitions

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
