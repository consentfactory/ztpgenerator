ztpgenerator: Zero Touch Provisioning Auto-config Generator
=

1. [Why does this exist?](#why-does-this-exist)
2. [What does it do:](#what-does-it-do)
3. [Prerequisites](#prerequisites) 
   - [Server Requirements](#server-requirements)
   - [Python Package Requirements](#python-package-requirements)
4. [Preconfiguration](#preconfiguration)
   - [ISC-DHCP](#isc-dhcp)
   - [<span>ztpgenerator.py</span>](#spanztpgeneratorpyspan)
5. [Workflow](#workflow)
   - [Preparing the Switch/Router/Firewall](#preparing-the-switchrouterfirewall)
     - [Juniper](#juniper)
   - [Inventory Devices](#inventory-devices)
     - [MAC Address](#mac-address)
     - [Serial Number](#serial-number)
   - [Populating CSV](#populating-csv)
     - ["mgmt_ip" vs "fixed_ip"](#mgmt_ip-vs-fixed_ip)
     - [Virtual Chassis](#virtual-chassis)
   - [Running ztpgenerator](#running-ztpgenerator)
6. [Customizing](#customizing)
7. [Troubleshooting](#troubleshooting)
   - [Check your data](#check-your-data)
   - [DHCP Issues](#dhcp-issues)
   - [<span>ztpgenerator.py</span> Issues](#spanztpgeneratorpyspan-issues)
8. [Gripes, Future Plans, Miscellaneous](#gripes-future-plans-miscellaneous)
9. [Notes and ack(s)](#notes-and-acks)

## Why does this exist?

I built this to solve the problem of deploying and upgrading Juniper switches, with the intention of expanding this possibly for Cisco switches. In my role I deploy (or redeploy) switches fairly often, and I just needed a simple approach to upgrading and loading them with a base configuration, with the intention that configuration management (Nornir, Ansible, etc.) can later refine their configs.

This addresses some of the manual configuration generation holes not filled by native ZTP on (currently) JunOS devices.

The script has been updated for Python 3, albeit by someone still develping Python skills. :-)

ZTP - Boots a fresh (new, out of the box) device, updates firmware, adds a config (usually a static configuration for all nodes that boot into ZTP).

<span>ztpgenerator.py</span> is a python script that generates configurations and static dhcpd reservations for each device. 

## What does it do:

1) Auto generation of static dhcp reservations (as an alternative to the randomized/pool model).

2) Customized network device configuration per switch (versus traditional ZTP sending a single static configuration for all devices), including virtual chassis configurations if desired. Currently Juniper only.

3) Specific operating system per switch. The main benefit here is if you have several device models that require different device images or versions.

## Prerequisites

### Server Requirements

This was designed to run on Debian-based servers (Ubuntu Server 18.04, in my case), but can certainly be ran on other Linux servers.

- ISC-DHCP
- Python 3.5+

### Python Package Requirements

**Jinja2** is the only Python package that needs to be installed before running the script. This can be installed easily via pip:

```bash
pip3 install jinja2
```

## Preconfiguration

There are few items that need to be preconfigured before using the ztpgenerator script. The ISC-DHCP server needs to be configured with the DHCP scope and Juniper ZTP settings, and the <span>ztpgenerator.py</span> script has variables relating to location of host file, configs, templates, etc.

### ISC-DHCP

The setup this was designed for is for one server hosting everything. I preprovision everything in a lab and only run the script when needed, therefore, my ISC-DHCP settings are pretty straight-forward.

As always create a backup of your dhcpd.conf file before making changes. CYA.

I have an example config located in [examples](/examples), but the gist of it is here:

```bash
# junos ztp options
option space ezjunosztp;
option ezjunosztp.image-file-name code 0 = text;
option ezjunosztp.config-file-name code 1 = text;
option ezjunosztp.image-file-type code 2 = text;
option ezjunosztp.transfer-mode code 3 = text;
option ezjunosztp-encap code 43 = encapsulate ezjunosztp;
option ezjunosztp-file-server code 150 = ip-address;

option domain-name "consentfactory.com";
option domain-name-servers 172.16.1.10;
default-lease-time 600;
max-lease-time 7200;

# subnet definition
subnet 172.16.1.0 netmask 255.255.255.0 {
        range dynamic-bootp 172.16.1.20 172.16.1.25;
        option routers 172.16.1.1;
}

# Host file containing the DHCP reservations
include "/etc/dhcp/hosts.conf";
```

Two of items of note:

1. I keep reservations and DHCP scope in different ranges so that if the device pulls a scope range address, I know something is configured right.
2. The host file is in the same location as the configuration.

The <span>ztpgenerator.py</span> script will create **one** backup of the hosts.conf file everytime the file is run.

### <span>ztpgenerator.py</span>

Your environment may vary, but as mentioned above, this is designed for a simple server setup, especially regarding the hosting of files for download. Customize the variables within <span>ztpgenerator.py</span> according to your own needs.

The variables needing adjustment:

```python
# Set this variable to your hosts.conf path that will contain your DHCP reservations
# e.g.  hosts_file="/etc/dhcp/hosts.conf"
hosts_file = "/etc/dhcp/hosts.conf"

# Set this variable to your web server path.
# e.g.  conf_path="/var/www/config/"
conf_path = "configs/"

# Set this variable to your templates path.
# e.g.  conf_path="$(pwd)/templates"
templates_path = "templates/"

# Command to restart your DHCP daemon (assuming Debian-based install)
# Change according to your server environment
dhcpd_restart_command="sudo systemctl restart isc-dhcp-server.service"

# Backup dhcp host file
backup_host = 'cp /etc/dhcp/hosts.conf /etc/dhcp/hosts.conf.backup'
os.system(backup_host)

# Remove host file for creation of new hosts file
remove_host_file = 'rm /etc/dhcp/hosts.conf'
os.system(remove_host_file)
```

## Workflow

High-level workflow:

1) Prepare the switch/router/firewall
2) Inventory your devices
3) Populate and export CSV to server
4) Run python script as root/sudo

### Preparing the Switch/Router/Firewall

In general, you'll want the device in a state for provisioning.

You'll want to also have a console cable available to check on things and monitor for any issues.

#### Juniper

For Juniper, you'll want an amnesiac switch or you can zerioize the switch with the following command:

```bash
request system zeroize
```

If monitoring via console, log-in as root and monitor the messages log:

```bash
monitor start messages
```

### Inventory Devices

The only technical requirement in ztpgenerator's default state is that you provide the following information:

- hostname (hostname)
- MAC address (mac_address)
- IP address (fixed_ip)
- Network device image name (junos_image)

Every other field is completely optional and relevant only to how you choose to set up your Jinja2 templates and deploy configurations.

#### MAC Address

Juniper - The actual mac address of your management interface can be calculated from the MAC on the barcode (box or on the network device). From my experience, take the barcode MAC and increment by 1 to the last digit.

Example:

```sh
Barcode mac is: aa:11:22:33:44:00
    me0 mac is: aa:11:22:33:44:01
```

You can also run the following command to get the management interface MAC, listed under 'Current Address':

```sh
show interface me0 media

Physical interface: me0    , Enabled, Physical link is Down
    ...
    Current address: aa:11:22:33:44:01
```

#### Serial Number

Juniper - If you're pre-provisioning Juniper switches for virtual chassis, you'll need the serial number. The serial number can typically be found on the barcode on the switch/box, or you can run the following command:

```sh
show chassis hardware

Hardware inventory:
Item             Version  Part number  Serial number     Description
Chassis                                NWXX111222222      EX3400-24P
```

### Populating CSV

As noted already, outside of the four CSV fields highlighted above, everything here is customizable. The field headers you put in the CSV will get turned into variables for the configuration templates, so you can add/remove as many variables as you would like.

For example, I added 'snmp_location' as a field, and then I configured my template like so:

```junos
snmp {
    location "{{ snmp_location }}";
    community public {
        authorization read-only;
    }
}
```

#### "mgmt_ip" vs "fixed_ip"

In my example CSV, I have IP address fields that differ from vloschiavo's version.

"mgmt_ip" is the field I use to configure the management IP address (in this case, I'm setting a L3 interface as a management address).

"fixed_ip" is the IP address I'm using for the DHCP reservation in ISC-DHCP.

#### Virtual Chassis

In the current version of ztpgenerator, I went with the expediated version of determining if virtual chassis configuration was desired by looking for 'vc' in the configuration template name (junos_template). Therefore, if you wish to configure the switches with virtual chassis, write your configuration template to include 'vc' in it's name; e.g., **junos_ex3400-vc.j2**.

Next, there are three CSV fields that are required:

- vc : Identifies the virtual chassis stack in cases where multiple stack configs are generated. **Numbering starts with 0**.
- vc_member_number : Sets the member number in the configuration. **Numbering starts with 0**.
- vc_role : Sets the virtual chassis role for the member. **Valid options include: role-engine, line-card**.

### Running ztpgenerator

The script should ran as sudo or root (sudo should be enough), and you need to provide the csv file name as an argument the script (the script will bark at you if you don't).

```bash
sudo ./ztp_configs.py device_data.csv
```

or

```bash
sudo python3 sudo ztp_configs.py device_data.csv
```

When running the script, the shell will let you know the web server is running and will display access information each time a device calls for a file. The web service will run indefinitely until 'Ctrl + C' is entered, which will stop the web service.

Note: the script is not designed to be ran all the time, although with some modifications it certainly could be.

## Customizing

Feel free to modify for your purposes.

## Troubleshooting

Various bits of troubleshooting advice.

### Check your data

_Make sure your data is accurate_. I once spent an entire afternoon in frustration because I had the wrong subnet configured for the 'fixed_ip' variables (it was one digit off).

### DHCP Issues

If you're having issues getting addresses, check to see if the service is running.

On Ubuntu:

```bash
sudo systemctl status isc-dhcp
```

Generally speaking, from my experience, most ISC-DHCP issues are related to the configuration file being misconfigured.

You can also follow the syslog while running the script to verify things are up and going:

```bash
# I'm using the -n flag to look for the last 50 lines
sudo tail -f /var/log/syslog -n 50
```

### <span>ztpgenerator.py</span> Issues

Most common issue for initial running of script: jinja2 module isn't installed. (See prereqs for info)

Next, there's usually a typo or a variable is configured correctly. Verify your variables are correct. Python should bark at you and tell you the line number where the issue is.

If there are any issues, they should appear when you first run the script.

## Gripes, Future Plans, Miscellaneous

- Wasn't sure where to put this, if at all, but I like to run this in a [Python virtual environment](https://realpython.com/python-virtual-environments-a-primer/), just to keep my module installs clean and separated from the global Python implementation.
- Cisco support: would definitely like to get this going because we have a mix of gear and it would nice to not have to perform artisinal work on these pets
- There is some logic in the script itself that I'm not satisfied with, some configurations that I put in for simplicity and off-loaded to the CSV file. Examples: 
  - Deciding virtual chassis configuration based on 'vc' in the template name. I mean, it works, but it could be better
  - Location of 'vcgenerator' call. I think the call should be in the logic function of determining virtual chassis configuration.
  - Could maybe remove the need for separate VC template by fixing vc logic
- Data validation needed for some components, such as vc, vc_member_number, etc.

## Notes and ack(s):

First off, this is a fork of [github.com/vloschiavo/ZTP](https://github.com/vloschiavo/ZTP), with ideas borrowed from [github.com/networkbootstrap/ztpmanager](https://github.com/networkbootstrap/ztpmanager) (largely the hosting of a web server versus ftp, and some other components). Giving credit where credit is due.

Juniper doc:
http://www.juniper.net/techpubs/en_US/release-independent/nce/information-products/topic-collections/nce/new-rtg-device/adding-a-new-network-device.pdf

It specifically applies to the section "Configuring New Routing Devices".

This is an extension to Juniper's basic ZTP. 
http://www.juniper.net/techpubs/en_US/junos13.3/topics/task/configuration/software-image-and-configuration-automatic-provisioning-confguring.html

Native ZTP allows you to apply a configuration to a new amnesiac device.  This extension creates ISC dhcpd.conf configurations as well as the JunOS configurations for an "unlimited" number of devices.

-Enjoy
