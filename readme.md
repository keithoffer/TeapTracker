ROMP TEAPTracker 0.0.9
=================

A program to interface with COMET to allow easier tracking of ROMP TEAP progress. I've only tested under Linux and Windows, but macOS should work aswell. If you don't want to run the python script itself, Windows [binary releases](https://github.com/keithoffer/TeapTracker/releases) are available through github.

![Screenshot showing_program](Screenshots/animated_preview.gif?raw=true)

A video demoing the program can be downloaded [here](https://www.dropbox.com/s/5njo2bqc9hzj5ck/teapTracker.mp4?dl=0)

Assumptions:
1) You never paused your TEAP program
2) You are only taking brachy to level 2 (it might still work if you submit brachy level 3's, but there will likely be strangeness as it's untested)

Prerequisites
-------------
- python 3.8+

For packages, see requirements.txt

Usage
-----

1) In the get data tab, enter your COMET username and password and click 'Get from Comet'
2) Wait for the program to get all your data from COMET

From here, your data is all downloaded for you to review. The main tabs are:

### Category Overview
Shows a grid based overview of your current progress. 

The y axis is each 'group' of competencies, each column is the level. Solid squared are signed off, hashed is uploaded but not signed off, and faded is unsubmitted.
Hovering over any competency shows the information from the CTG on the right.
You can middle click on any competency to leave a note, which will then show on hover.
You can left click the competency to highlight it in blue, and also adds it to your training plan (see the 'Tracking' tab)

### Scores
Shows a table with one row per competency. 

Clicking on any row shows the supervisor comments for the submission. 
You can sort by any column heading, and filter based on submission and graded status. For example, filtering by submission status 'Submitted' and grading status 'Not graded' will make a list of all competencies currently requiring sign off by the supervisor.

### Module Overview
Shows a barchart with total points out of available points per competency. 

You can view this as absolute points or relative completion.
Same as the Category Overview tab, solid is signed off, hashed is uploaded and not graded, faded is not submitted.

### Tracking
Shows a line plot showing how your points total tracks as compared to the college expectation.

If incorrect, you can adjust your length of program and start date at the top of the tab.
The plot shows expected (green), actual (orange) and uploaded (blue). The uploaded line assumes everything you upload is worth full marks, and useful to assess progress if there is a lag between uploads and signoffs.
At the bottom of the tab, you have two further options:
1) You can show a simple extrapolation of progress, looking at your uploaded progress X months ago and now
2) You can show your plan. The plan will be the sum of points of all competencies clicked (highlighted blue) in the 'Category Overview' tab. You can set your start and end date, and track your progress to see if you're meeting your goal.

### Misc

The misc tab shows some stats that may be of interest:

1) Number of signed off competencies, partially signed off and not signed off competencies, also as a percentage
2) How many are currently waiting on grading
3) The average time between upload and sign off (mean differences between last modified date and graded date)

### Get data

1) If your data on COMET is updated, you'll need to re-enter your username and password and re-download your data.
2) You can store multiple registrar's data in the cached_data folder of the program. If there is only one set of data, it will automatically load them on program start. If there are more than 1, you need to select which registrar to load here. This is useful to compare yourself to another registrar, or for a supervisor to compare multiple registrar's progress.

Known issues
------------

1) Sometimes the note in the 'Category Overview' tab goes off the side of the image, and you can't see it. I've tried multiple fixes but none have worked. Just middle click to see the note in the edit window if this occurs.
2) It can take a long time between double clicking the Windows .exe and the application launching. This is due to the way it's packaged, I'm open to any ideas on how to improve this.

Acknowledgements
------------

- Some of the labels on the vertical axis of the 'Category Overview' plot are based on a tracking spreadsheet made by Stephanie Keehan.
- This work relies on multiple python packages under varying licenses. See the requirements.txt and pypi for more information, or contact me for more information.

License
-------

ROMP TEAPTracker is copyrighted free software made available under the terms of the GPLv3

Copyright: (C) 2021 by Keith Offer. All Rights Reserved.