# NParkerThesisWetlandsHyperspec

Code and analysis pipeline for hyperspectral wetland soil analysis.

This repository contains scripts for extracting and analyzing spectral
signatures from airborne hyperspectral imagery (NEON ROCX).

## Repository Structure

src/scripts  
Python scripts used for ROI extraction, spectral plotting, and analysis.

data/processed  
CSV reference points and intermediate data products.

notebooks  
Exploratory analysis notebooks.

outputs  
Generated figures and summaries (not tracked by Git).

## Data

Raw hyperspectral imagery (.h5, .tif) is not included due to file size.
Place raw files in:

data/raw/

## Environment

Python environment dependencies can be recreated using:

pip install -r requirements.txt