# Shapez2Analyzer - Shape Simulator and Analysis Tool

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-GUI-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## Installation

```bash
pip install -r requirements.txt
```

## Run

```bash
python gui.py
```

## Build

```bash
build.bat
```

## Features

- **Shape Simulation**: Shape Code input, Operations, Analysis and Visualisation
- **Inverse Operations**: Find original shapes from target shapes
- **Shape Classification**: Automatic shape type detection
- **Process Tree**: Visualize shape creation process
- **Batch Processing**: Handle large amounts of shape data

## TODO

- ~~**Process Tree**: Implement process tree visualization~~
- ~~**Claw Hybrid**: Implement claw and hybrid shape analysis~~
- Writing program user documentation(Video guide)
- Scaling beyond 6 floors
- Expand quadrants like hexmode
- Fixing bugs
- Optimisation and refactoring

## Issues

- Claw Hybrid / Complex Hybrid / Claw Complex Hybrid are not distinguished well.
- Classification of shapes is being called recursively.
- Unused py files are left.

## Project Structure

```
Shapez2/
├── gui.py                 # Main GUI application
├── shape.py               # Core shape classes and operations
├── shape_classifier.py    # Shape classification system
├── process_tree_solver.py # Process tree generation
├── corner_tracer.py       # Corner tracing algorithm
├── hybrid_tracer.py       # Hybrid shape tracing algorithm
├── claw_tracer.py         # Claw tracing algorithm
├── claw_hybrid_tracer.py  # Claw hybrid tracing algorithm
├── data_operations.py     # Data processing utilities
├── data/                  # Data files directory
├── icons/                 # Application icons
├── locales/               # Internationalization files
├── docs/                  # Documentation
```
