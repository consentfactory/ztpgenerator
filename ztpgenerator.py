#!/usr/bin/python3

# Import the necessary modules
import csv
import sys
from jinja2 import Template
import http.server
import socketserver
import signal
import os

# Helps with Ctrl-C errors
signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # IOError: Broken pipe
signal.signal(signal.SIGINT, signal.SIG_DFL)  # KeyboardInterrupt: Ctrl-C

# For the variables below to work you'll need to run the script as the appropriate user / credentials.
# All variables are for Debian-based locations  
# sudo should work fine.  If the script boms, check your paths and permissions.

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

# Setting up VC Configuration dictionary
vc_configuration = {}

##################################################
# End: User defined variables
# Beyond here be dragons
##################################################

# Generates dictionary for virtual chassis configurations
def vcgenerator(csv_file):
    csv_filename = csv_file

    # Read device_data.csv from the current directory
    # csv.DictReader reads the first row as a header row and stores the column headings as keys
    device_data = csv.DictReader(open(csv_filename))

    # Setting up list of Virtual Chassis items to loop through later
    vc_list = []

    # Setting up dictionary that will contain all VCs and child members
    vc_dict = {}

    # VC Configuration Template
    with open("{}junos/junos_vc.j2".format(templates_path)) as vc_jinja_template:
                vc_format = vc_jinja_template.read()

    # Loops through the device_data csv so we can perform actions for each row
    for row in device_data:
        # If the VC number in the CSV is not in the list already and isn't blank, add to the list
        if (row['vc'] not in vc_list) and (row['vc'] is not ""):
            vc_list.append(row['vc'])
        # If the VC number isn't blank, add it as a dictionary item
        if row['vc'] is not "":
            vc_item = vc_dict.get(row['vc'], dict())
            vc_dict[row['vc']] = vc_item

    # Loop through the VC items in the VC list
    # When I initially looped through vc_dict, the dictionary would be updated and then 
    # it couldn't be looped through. Using the vc_list to resolve this since this is a one-time
    # pass-through
    for vc in vc_list:
        # The previous device_data is no longer available, so initializing a new instance of the CSV
        device_data_2 = csv.DictReader(open(csv_filename))
        # Creating a child dictionary that will contain the virtual chassis members
        vc_member = {}
        # Looping through the CSV again to get chassis memberships
        for row in device_data_2:
            # If row['vc'] item isn't blank and is part of the current vc in our looping through
            # vc_list, create a dictionary item with the key of the vc_member_number and add
            # serial number and member number as key:values in dictionary item
            if (row['vc'] is not "") and (row['vc'] is vc):
                # Create the new key with a value of another dictionary
                vc_item = vc_member.get(row['vc_member_number'], dict())
                # Add serial number and vc member number as key:values
                vc_item['serial'] = row['serial_number']
                vc_item['member'] = row['vc_member_number']
                vc_item['role'] = row['vc_role']
                # Add the new dictionary as the value of the member key
                vc_member[row['vc_member_number']] = vc_item

        # Add the new vc_member dictionary as a key:value to the vc item in vc_dict, thereby
        # creating multiple members to the parent vc key
        vc_dict.update({vc:vc_member})
    
    for vc_key,members in vc_dict.items():
        template = Template(vc_format)
        vc_config_value = template.render(members=members)
        vc_item = vc_configuration.get(vc_key, vc_config_value)
        vc_configuration[vc_key] = vc_item

# Main ZTP Generator
def ztpgenerator(csv_file):
    # File name of your csv file
    csv_filename = csv_file
    
    # Read device_data.csv from the current directory
    # csv.DictReader reads the first row as a header row and stores the column headings as keys
    device_data = csv.DictReader(open(csv_filename))

    print("\nGenerating device and dhcpd config files...\n")
    # Loops through the device_data csv so we can perform actions for each row
    for row in device_data:
        
        ### Config Generation ###
        
        # Stores the contents of each "cell" as the value for the column header
        # key : value pair
        data = row

        # creates a filename variable for the JunOS configuration based on the hostname in the CSV
        junos_conf_filename =  conf_path + row["hostname"] + ".conf"

        # Check to see if template chosen is a virtual chassis template
        if "vc" in row["junos_template"]:
            # Open the Junos config Jinja2 template file.
            with open("{}junos/{}".format(templates_path,row["junos_template"])) as t_fh:
                t_format = t_fh.read()

            # Send to Jinja2 object and set it up as a template
            junos_template = Template(t_format)

            # Create the .conf file
            fout = open(junos_conf_filename, 'w')
            #print(fout)

            # Write the Junos conf file with the template and data from the current row
            # Performs a "search and replace"
            fout.write((junos_template.render(data,vc_config=vc_configuration[row['vc']])))
            fout.close()
        # If template is not a virtual chassis template, create non-vc config
        else:
            # Open the Junos config Jinja2 template file.
            with open("{}junos/{}".format(templates_path,row["junos_template"])) as t_fh:
                t_format = t_fh.read()

            # Send to Jinja2 object and set it up as a template
            junos_template = Template(t_format)

            # Create the .conf file
            fout = open(junos_conf_filename, 'w')
            #print(fout)

            # Write the Junos conf file with the template and data from the current row
            # Performs a "search and replace"
            fout.write((junos_template.render(data)))
            fout.close()

        ### END Config Generation ###

        ### ISC-DHCP Section ###
        
        # Create the ISC-DHCPd config for this node
        # Read the dhcpd Jinja2 template file.
        with open("{}dhcpd/dhcpd.j2".format(templates_path)) as t2_fh:
            t2_format = t2_fh.read()

        # Set it up as a template
        dhcpd_template = Template(t2_format)

        # Print to SDOUT. Uncomment for debugging
        #print (template2.render(data))

        # Write or append switch host to dhcp hosts file
        with open(hosts_file, "a") as hostsconf:
            hostsconf.write(dhcpd_template.render(data))

        # Restart dhcpd
        from subprocess import call
        call(dhcpd_restart_command, shell=True)

    print("Done generating config files...\n")

# Running Simple HTTP server to act as HTTP file server
# After done, hit 'Ctrl + C' to close HTTP service
def http_server():
    port = 80
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(('', port), handler) as httpd:
        print("Running HTTP Server...\nPress \"Ctrl+C\" in console to close HTTP server.")
        httpd.serve_forever()

if __name__ == '__main__':
    if len(sys.argv) < 1:
        print('Usage: sudo python3 ztpgenerator.py csv_file.csv')
        exit(1)
    
    csv_file = sys.argv[1]

    vcgenerator(csv_file)

    ztpgenerator(csv_file)

    http_server()
