# Rhode Schwarz SMY02 Signal Generator Controller

Python application for controlling the Rhode Schwarz SMY02 signal generator via GPIB/USB interface.

## Features

- GPIB/USB communication with SMY02 signal generator
- Frequency and amplitude control
- Modulation configuration
- Data logging and export
- GUI interface for control and monitoring

## Requirements

- Python 3.8+
- GPIB/USB interface hardware
- Rhode Schwarz SMY02 signal generator

## Installation

1. Clone or download this project
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Basic Command Line Control

```python
from src.smy02_controller import SMY02Controller

controller = SMY02Controller(resource_name="GPIB0::16::INSTR")
controller.connect()
controller.set_frequency(1e9)  # 1 GHz
controller.set_amplitude(0)    # 0 dBm
controller.enable_output()
controller.disconnect()
```

### GUI Application

```bash
python -m src.gui.main
```

## Project Structure

```
Generator/
├── src/
│   ├── smy02_controller.py    # Main controller class
│   ├── gui/
│   │   └── main.py            # GUI application
│   └── utils/
│       └── logger.py           # Data logging utilities
├── tests/
│   └── test_controller.py     # Unit tests
├── docs/
│   └── smy02_manual.md        # Device documentation
├── requirements.txt            # Python dependencies
└── README.md
```

## Configuration

Before connecting, ensure your GPIB/USB interface is properly configured:

1. Check available instruments:
   ```bash
   python -c "import pyvisa; rm = pyvisa.ResourceManager(); print(rm.list_resources())"
   ```

2. Update the resource name in your code accordingly

## License

MIT License
