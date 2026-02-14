<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# SMY02 Signal Generator Controller - Development Guidelines

## Project Overview
Python application for controlling Rhode Schwarz SMY02 signal generator via GPIB/USB communication.

## Key Technologies
- **PyVISA**: GPIB/USB instrument communication
- **PyQt5**: GUI framework (optional)
- **Matplotlib**: Data visualization
- **NumPy**: Numerical operations

## Development Standards

### Code Style
- PEP 8 compliant
- Type hints for function signatures
- Docstrings for all public methods
- Error handling for VISA communication

### Device Communication
- Use PyVISA for all instrument control
- Implement proper connection/disconnection handling
- Add timeouts for all VISA operations
- Log all commands and responses

### Testing
- Unit tests for controller functions
- Mock VISA communication for offline testing
- Test error conditions and edge cases

### Documentation
- Update README.md when adding features
- Include command examples in docstrings
- Document SCPI commands used
