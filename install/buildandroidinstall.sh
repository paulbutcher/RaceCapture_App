#!/bin/bash

promptyn () {
    while true; do
        read -p "$1 " yn
        case $yn in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo "Please answer yes or no.";;
        esac
    done
}

pushd ~/android/python-for-android
if promptyn "Rebuild the Python on Android distribution? Only needs to be done if you've changed which prereqs are installed, or upgraded Kivy, or that sort of thing. Oh yeah, also it takes absolutely ages. [Y/N]"; then
	rm -rf dist
	rm -rf build
	# for some reason adding pygments to this (either before or after kivy) doesn't work
	./distribute.sh -m "kivy"
fi
	
pushd ~/android/python-for-android/dist/default
./build.py --dir ~/RaceCapture_App --package com.racecapture.racecapture --name "RaceCapture" --version 0.0.1 debug installd
echo "Monitoring Android LogCat... Ctrl-C if you're not interested in that!"
~/android/android-sdk-linux/platform-tools/adb logcat | grep python
