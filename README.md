# pentair_cloud
Homeassistant Pentair cloud custom integration.
Supports the Pentair IntelliFlo 3 VS Pump with the Wifi module. This integration will create a virtual "Light" for each of the programs you have configured in your Pentair Home App. You can use this to:
- Start/Stop a program
- Know when a program is running
Data is pulled from the Pentair Web service used by the Pentair Home App.
Note: This project is not associated with or endorsed by Pentair.

Example Scenario: I have a Program in my Pentair Home App for when I want to run my pool cleaner. My pool cleaner is connected to a sonoff relay. Using this integration, I can detect when the pump is running the "cleaner program" and turn on the pool cleaner.
## Installation with HACS

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

The simplest way to install this integration is with the Home Assistant Community Store (HACS). This is not (yet) part of the default store and will need to be added as a custom repository.

Setting up a custom repository is done by:

1. Go into HACS from the side bar.
2. Click into Integrations.
3. Click the 3-dot menu in the top right and select `Custom repositories`
4. In the UI that opens, copy and paste the [url for this github repo](https://github.com/SPD13/pentair_cloud) into the `Add custom repository URL` field.
5. Set the category to `Integration`.
6. Click the `Add` button. Further configuration is done within the Integrations configuration in Home Assistant. You may need to restart home assistant and clear your browser cache before it appears, try ctrl+shift+r if you don't see it in the configuration list.

## Manual Installation

If you don't want to use HACS or just prefer manual installs, you can install this like any other custom component. Just merge the `custom_components` folder with the one in your Home Assistant config folder and you may need to manually install the `pycognito` and `requests-aws4auth` library.
