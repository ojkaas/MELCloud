# MELCloud for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

This [Home Assistant](https://www.home-assistant.io/) service allows you to integrate Mitsubishi Electric’s MELCloud enabled devices into Home Assistant. It extends the core integration [MELCloud](https://www.home-assistant.io/integrations/melcloud/) with ERV Support

## Installation

**Method 1.** [HACS](https://hacs.xyz/) custom repo:

> HACS > Integrations > 3 dots (upper top corner) > Custom repositories > URL: `ojkaas/MELCloud`, Category: Integration > Add > wait > MELCloud (With ERV Support) > Install

**Method 2.** Manually copy `melcloud` folder from [latest release](https://github.com/ojkaas/melcloud/releases/latest) to `/config/custom_components` folder.

## Configuration

**Method 1.** GUI:

> Configuration > Integrations > Add Integration > **MELCloud (With ERV Support)**

If the integration is not in the list, you need to clear the browser cache.

Check the core integration for further details: [MELCloud](https://www.home-assistant.io/integrations/melcloud/)