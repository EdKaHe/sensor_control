# -*- coding: utf-8 -*-
"""
Created on Thu Nov  9 17:44:49 2017

@author: Ediz
"""

import serial
from serial.tools.list_ports import comports
from bokeh.io import curdoc
from bokeh.models import PanTool, ResetTool, WheelZoomTool, SaveTool, HoverTool, ColumnDataSource
from bokeh.models.widgets import RadioButtonGroup, Button, Slider
from bokeh.models.callbacks import CustomJS
from bokeh.layouts import layout
from bokeh.plotting import figure
from time import time, sleep
from datetime import datetime
from pytz import timezone
from PyCRC.CRC16 import CRC16
import paramiko
import pandas as pd

#bokeh serve --allow-websocket-origin=localhost:5000 sensor_control.py

#get start time of script
start_time = time()

#create columndatasource
source = ColumnDataSource(dict(time=[], photo_current=[], laser_current=[], date=[]))

#connect to port
port_name = 'USB Serial Port (COM3)'

#host credentials
credentials=pd.read_json(r'./credentials.JSON', typ='series')
server = credentials['server']
port = int(credentials['port'])
username = credentials['username']
password = credentials['password']

#connect to server and generate csv file
filename_all_data='/opt/webapps/sensor_surveillance/data/sc_all_data.csv' #this file will contain all data
filename_new_data='/opt/webapps/sensor_surveillance/data/sc_new_data.csv' #this file will contain the newest data for streaming it
cmd_create_csv = 'mkdir -p /opt/webapps/sensor_surveillance/data; rm -f /opt/webapps/sensor_surveillance/data; echo time\;photo_current\;laser_current\;date >'
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(server, port=port, username=username, password=password,timeout=10)
ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd_create_csv+filename_all_data)
ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd_create_csv+filename_new_data)

#Dictionary with commands to control the sensor electronics
commands = {'set laser off': b'\r0108W030000085C6\n',
           'set laser on': b'\r0108W03000014507\n',
           'set laser current': '0108W01',
           'get laser current': b'\r0103R016714\n',
           'get photo current': b'\r0108R0639441B2C3\n',
           }
    
#create figure
f_photo = figure(tools=[PanTool(), WheelZoomTool(), ResetTool(), SaveTool()],output_backend='webgl')
hover=HoverTool(tooltips=[('Date', '@date')])
f_photo.add_tools(hover)
f_photo.toolbar.logo = None
#f_photo.output_backend = 'svg'

f_laser = figure(tools=[PanTool(), WheelZoomTool(), ResetTool(), SaveTool()],output_backend='webgl')
hover=HoverTool(tooltips=[('Date', '@date')])
f_laser.add_tools(hover)
f_laser.toolbar.logo = None
#f_laser.output_backend = 'svg'

#initialize port and read the photocurrent
def read_value():
#    ports=comports()
#    for port in ports:
#        if str(port[1])==port_name:
#            ser = serial.Serial(str(port[0]),baudrate=115200,timeout=200)
#    #read photo_current        
#    ser.write(commands['get photo current'])
#    photo_current=int(ser.read(18)[8:13].decode('ascii')) #8:13 contains value
#    sleep(0.1)
#    #read laser current
#    ser.write(commands['get laser current'])
#    laser_current=int(ser.read(18)[8:13].decode('ascii'))
#    ser.close()
    photo_current=1
    laser_current=1
    return photo_current, laser_current

#create function to switch laser on and off
def laser_change(attr, old, new):
    ports=comports()
    for port in ports:
        if str(port[1])==port_name:
            ser = serial.Serial(str(port[0]),baudrate=115200,timeout=200)
    ser.write(commands[opt2cmd[radio_button_group.active]])
    ser.close()
    if opt2cmd[radio_button_group.active]=='set laser off':   
        slider.value = 0
    elif opt2cmd[radio_button_group.active]=='set laser on':
        slider.value= 100
    
def laser_power(attr, old, new):
    check_str = commands['set laser current'] + str(int(slider.value*2.55)).zfill(5)
    command_str = '\r'+check_str+calc_crc16modbus(check_str)+'\n'
    command_str = str.encode(command_str)
    ports=comports()
    for port in ports:
        if str(port[1])==port_name:
            ser = serial.Serial(str(port[0]),baudrate=115200,timeout=200)
    ser.write(command_str)
    ser.close()
    
#calculate crc16 modbus checksum
def calc_crc16modbus(check_str):
    return '{:X}'.format(CRC16(modbus_flag=True).calculate(str.encode(check_str))).zfill(4) #Fill checksum to 4 digits

#create periodic function
def update():
    dt = time() - start_time
    photo_current, laser_current = read_value()
    new_data=dict(time=[dt], photo_current=[photo_current], laser_current= [laser_current], date=[datetime.strftime(datetime.now(tz=timezone('Europe/Berlin')),'%d. %b %y %H:%M:%S')])
    source.stream(new_data)#,rollover=400) #how many glyphs/circles are kept in plot
    
    #update new data in csv
    cmd_update_header='echo time\;photo_current\;laser_current\;date >' + filename_new_data
    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd_update_header)
    cmd_update_data = 'echo  '+'{:.2f}'.format(source.data['time'][-1])+'\;'+str(source.data['photo_current'][-1])+'\;'+str(source.data['laser_current'][-1])+'\;'+str(source.data['date'][-1])+' >> ' + filename_new_data
    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd_update_data)
    
    #store all data in anoter csv
    cmd_store_data = 'echo  '+'{:.2f}'.format(source.data['time'][-1])+'\;'+str(source.data['photo_current'][-1])+'\;'+str(source.data['laser_current'][-1])+'\;'+str(source.data['date'][-1])+' >> ' + filename_all_data
    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(cmd_store_data)
                                                         
#create glyphs
#f.circle(x='time', y='photo_current', color='firebrick', line_color=None, size=8, fill_alpha=0.4, source=source)
f_photo.circle(x='time', y='photo_current', size=10, line_color='gray', fill_color='gray', line_alpha=1, fill_alpha=0.3, source=source)

f_laser.circle(x='time', y='laser_current', size=10, line_color='firebrick', fill_color='firebrick', line_alpha=1, fill_alpha=0.3, source=source)

#Style the plot area
f_photo.plot_width = 900
f_photo.plot_height = 400
f_photo.background_fill_color=None
f_photo.border_fill_color=None

f_laser.plot_width = 900
f_laser.plot_height = 200
f_laser.background_fill_color=None
f_laser.border_fill_color=None

#Style the axes
f_photo.axis.minor_tick_line_color='black'
f_photo.axis.minor_tick_in=-6
f_photo.yaxis.axis_label='Signal Current (arb. units)'
f_photo.axis.axis_label_text_color=(0.7,0.7,0.7)
f_photo.axis.major_label_text_color=(0.7,0.7,0.7)
f_photo.axis.axis_label_text_font = 'helvetica'
f_photo.yaxis.axis_label_text_font_size = '16pt'
f_photo.axis.axis_label_text_font_style = 'normal'
f_photo.axis.major_label_text_font = 'helvetica'
f_photo.axis.major_label_text_font_size = '10pt'
f_photo.axis.major_label_text_font_style = 'normal'

f_laser.axis.minor_tick_line_color='black'
f_laser.axis.minor_tick_in=-6
f_laser.xaxis.axis_label='Time in (s)'
f_laser.yaxis.axis_label='Laser Current'
f_laser.axis.axis_label_text_color=(0.7,0.7,0.7)
f_laser.axis.major_label_text_color=(0.7,0.7,0.7)
f_laser.axis.axis_label_text_font = 'helvetica'
f_laser.axis.axis_label_text_font_size = '16pt'
f_laser.axis.axis_label_text_font_style = 'normal'
f_laser.axis.major_label_text_font = 'helvetica'
f_laser.axis.major_label_text_font_size = '10pt'
f_laser.axis.major_label_text_font_style = 'normal'

#Style the title
f_photo.title.text='Hydrogen Control'
f_photo.title.text_color=(0.7,0.7,0.7)
f_photo.title.text_font='helvetica'
f_photo.title.text_font_size='20pt'
f_photo.title.align='left'

#Style the grid
f_photo.grid.grid_line_color=(1,1,1)
f_photo.grid.grid_line_alpha=0.3
f_photo.grid.grid_line_dash=[5,3]

f_laser.grid.grid_line_color=(1,1,1)
f_laser.grid.grid_line_alpha=0.3
f_laser.grid.grid_line_dash=[5,3]

#add widgets (radio button group)
options=['Laser on', 'Laser off']
opt2cmd=['set laser on', 'set laser off']
radio_button_group = RadioButtonGroup(labels=options)
radio_button_group.on_change('active', laser_change)

#add widgets (slider)
slider = Slider(start=0, end=100, value=100, step=1, title='Laser power (%)')
slider.on_change('value', laser_power)

#add widgets (dropdown button)/currently there is only the possibility to save as csv
button = Button(label='Export data', button_type='danger')
js_download = """
var csv = source.get('data');
var filetext = 'time;photo_current;laser_current;date\\n';
for (i=0; i < csv['date'].length; i++) {
    var currRow = [csv['time'][i].toString(),
                   csv['photo_current'][i].toString(),
                   csv['laser_current'][i].toString(),
                   csv['date'][i].toString().concat('\\n')];

    var joined = currRow.join(';');
    filetext = filetext.concat(joined);
}

var filename = 'sensor_data.csv';
var blob = new Blob([filetext], { type: 'text/csv;charset=utf-8;' });
if (navigator.msSaveBlob) { // IE 10+
navigator.msSaveBlob(blob, filename);
} else {
var link = document.createElement("a");
if (link.download !== undefined) { // feature detection
    // Browsers that support HTML5 download attribute
    var url = URL.createObjectURL(blob);
    link.setAttribute("href", url);
    link.setAttribute("download", filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
}"""
button.callback = CustomJS(args=dict(source=source), code=js_download)

#add figure to curdoc and configure callback
lay_out=layout([[radio_button_group, slider],[f_photo],[f_laser],[button]])
curdoc().add_root(lay_out)
curdoc().add_periodic_callback(update,1000) #updates each 1000ms