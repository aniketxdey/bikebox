"""
ble_server.py — BLE GATT Peripheral for BikeBox.

Creates a BlueZ GATT server with:
  - BikeBox Service (CB000001-...)
  - Crash Alert Characteristic (CB000002-...) — Notify
  - Device Status Characteristic (CB000003-...) — Read, Notify
  - Grace Period Characteristic (CB000004-...) — Read, Write, Notify

Uses the D-Bus API to register with BlueZ. Requires:
  - BlueZ with --experimental flag enabled
  - python3-dbus and python3-gi packages
"""

import struct
import threading
import time
from typing import Callable, Optional

try:
    import dbus
    import dbus.exceptions
    import dbus.mainloop.glib
    import dbus.service
    from gi.repository import GLib
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False

from config import (
    BLE_SERVICE_UUID, BLE_CRASH_ALERT_UUID,
    BLE_DEVICE_STATUS_UUID, BLE_GRACE_PERIOD_UUID,
    BLE_HOTSPOT_CONTROL_UUID, BLE_LOCAL_NAME,
    HOTSPOT_OFF
)

BLUEZ_SERVICE_NAME = 'org.bluez'
GATT_MANAGER_IFACE = 'org.bluez.GattManager1'
LE_ADVERTISING_MANAGER_IFACE = 'org.bluez.LEAdvertisingManager1'
DBUS_OM_IFACE = 'org.freedesktop.DBus.ObjectManager'
DBUS_PROP_IFACE = 'org.freedesktop.DBus.Properties'
GATT_SERVICE_IFACE = 'org.bluez.GattService1'
GATT_CHRC_IFACE = 'org.bluez.GattCharacteristic1'
GATT_DESC_IFACE = 'org.bluez.GattDescriptor1'
LE_ADVERTISEMENT_IFACE = 'org.bluez.LEAdvertisement1'
AGENT_IFACE = 'org.bluez.Agent1'
AGENT_MANAGER_IFACE = 'org.bluez.AgentManager1'


if DBUS_AVAILABLE:
    class Application(dbus.service.Object):
        """D-Bus application object that contains GATT services."""

        PATH_BASE = '/org/bikebox'

        def __init__(self, bus):
            self.path = self.PATH_BASE
            self.services = []
            dbus.service.Object.__init__(self, bus, self.path)
            self.add_service(BikeBoxService(bus, 0))

        def get_path(self):
            return dbus.ObjectPath(self.path)

        def add_service(self, service):
            self.services.append(service)

        @dbus.service.method(DBUS_OM_IFACE, out_signature='a{oa{sa{sv}}}')
        def GetManagedObjects(self):
            response = {}
            for service in self.services:
                response[service.get_path()] = service.get_properties()
                for chrc in service.get_characteristics():
                    response[chrc.get_path()] = chrc.get_properties()
                    for desc in chrc.get_descriptors():
                        response[desc.get_path()] = desc.get_properties()
            return response


    class Service(dbus.service.Object):
        """BlueZ GATT Service."""

        def __init__(self, bus, index, uuid, primary):
            self.path = f'/org/bikebox/service{index}'
            self.bus = bus
            self.uuid = uuid
            self.primary = primary
            self.characteristics = []
            dbus.service.Object.__init__(self, bus, self.path)

        def get_properties(self):
            return {
                GATT_SERVICE_IFACE: {
                    'UUID': self.uuid,
                    'Primary': self.primary,
                    'Characteristics': dbus.Array(
                        self.get_characteristic_paths(), signature='o'
                    )
                }
            }

        def get_path(self):
            return dbus.ObjectPath(self.path)

        def add_characteristic(self, characteristic):
            self.characteristics.append(characteristic)

        def get_characteristic_paths(self):
            return [c.get_path() for c in self.characteristics]

        def get_characteristics(self):
            return self.characteristics

        @dbus.service.method(DBUS_PROP_IFACE, in_signature='s',
                             out_signature='a{sv}')
        def GetAll(self, interface):
            if interface != GATT_SERVICE_IFACE:
                raise dbus.exceptions.DBusException(
                    'org.freedesktop.DBus.Error.InvalidArgs')
            return self.get_properties()[GATT_SERVICE_IFACE]


    class Characteristic(dbus.service.Object):
        """BlueZ GATT Characteristic."""

        def __init__(self, bus, index, uuid, flags, service):
            self.path = f'{service.get_path()}/char{index}'
            self.bus = bus
            self.uuid = uuid
            self.service = service
            self.flags = flags
            self.descriptors = []
            self.value = []
            self.notifying = False
            dbus.service.Object.__init__(self, bus, self.path)

        def get_properties(self):
            return {
                GATT_CHRC_IFACE: {
                    'Service': self.service.get_path(),
                    'UUID': self.uuid,
                    'Flags': self.flags,
                    'Descriptors': dbus.Array(
                        self.get_descriptor_paths(), signature='o'
                    )
                }
            }

        def get_path(self):
            return dbus.ObjectPath(self.path)

        def add_descriptor(self, descriptor):
            self.descriptors.append(descriptor)

        def get_descriptor_paths(self):
            return [d.get_path() for d in self.descriptors]

        def get_descriptors(self):
            return self.descriptors

        @dbus.service.method(DBUS_PROP_IFACE, in_signature='s',
                             out_signature='a{sv}')
        def GetAll(self, interface):
            if interface != GATT_CHRC_IFACE:
                raise dbus.exceptions.DBusException(
                    'org.freedesktop.DBus.Error.InvalidArgs')
            return self.get_properties()[GATT_CHRC_IFACE]

        @dbus.service.method(GATT_CHRC_IFACE, in_signature='a{sv}',
                             out_signature='ay')
        def ReadValue(self, options):
            return self.value

        @dbus.service.method(GATT_CHRC_IFACE, in_signature='aya{sv}')
        def WriteValue(self, value, options):
            self.value = value

        @dbus.service.method(GATT_CHRC_IFACE)
        def StartNotify(self):
            self.notifying = True

        @dbus.service.method(GATT_CHRC_IFACE)
        def StopNotify(self):
            self.notifying = False

        @dbus.service.signal(DBUS_PROP_IFACE, signature='sa{sv}as')
        def PropertiesChanged(self, interface, changed, invalidated):
            pass

        def send_notification(self, value):
            """Send a GATT notification with the given value bytes.

            Schedules the D-Bus signal on the GLib main loop thread to
            avoid cross-thread D-Bus errors that cause BLE disconnects.
            """
            if not self.notifying:
                return

            def _emit():
                try:
                    self.value = dbus.Array(value, signature='y')
                    self.PropertiesChanged(
                        GATT_CHRC_IFACE,
                        {'Value': self.value},
                        []
                    )
                except Exception as e:
                    print(f"BLE: Notification error: {e}")
                return False

            GLib.idle_add(_emit)


    class PairingAgent(dbus.service.Object):
        """NoInputNoOutput agent that auto-accepts BLE Just Works pairing.

        Without this agent, BlueZ has no way to complete pairing — every
        connection attempt triggers a pairing request that fails, causing
        the central (iOS) to see a disconnect and retry in a loop.
        """

        AGENT_PATH = '/org/bikebox/agent'

        def __init__(self, bus):
            dbus.service.Object.__init__(self, bus, self.AGENT_PATH)

        @dbus.service.method(AGENT_IFACE, in_signature='', out_signature='')
        def Release(self):
            pass

        @dbus.service.method(AGENT_IFACE, in_signature='os', out_signature='')
        def AuthorizeService(self, device, uuid):
            print(f"BLE Agent: Authorizing service {uuid} for {device}")

        @dbus.service.method(AGENT_IFACE, in_signature='o', out_signature='')
        def RequestAuthorization(self, device):
            print(f"BLE Agent: Auto-authorizing {device}")

        @dbus.service.method(AGENT_IFACE, in_signature='o', out_signature='s')
        def RequestPinCode(self, device):
            return '0000'

        @dbus.service.method(AGENT_IFACE, in_signature='o', out_signature='u')
        def RequestPasskey(self, device):
            return dbus.UInt32(0)

        @dbus.service.method(AGENT_IFACE, in_signature='ouq', out_signature='')
        def DisplayPasskey(self, device, passkey, entered):
            pass

        @dbus.service.method(AGENT_IFACE, in_signature='ou', out_signature='')
        def RequestConfirmation(self, device, passkey):
            print(f"BLE Agent: Auto-confirming passkey for {device}")

        @dbus.service.method(AGENT_IFACE, in_signature='', out_signature='')
        def Cancel(self):
            pass


    class BikeBoxService(Service):
        """The main BikeBox GATT service with all characteristics."""

        def __init__(self, bus, index):
            super().__init__(bus, index, BLE_SERVICE_UUID, True)

            self.crash_alert_chrc = Characteristic(
                bus, 0, BLE_CRASH_ALERT_UUID, ['notify'], self
            )
            self.device_status_chrc = Characteristic(
                bus, 1, BLE_DEVICE_STATUS_UUID, ['read', 'notify'], self
            )
            self.grace_period_chrc = GracePeriodCharacteristic(bus, 2, self)
            self.hotspot_control_chrc = HotspotControlCharacteristic(bus, 3, self)

            self.add_characteristic(self.crash_alert_chrc)
            self.add_characteristic(self.device_status_chrc)
            self.add_characteristic(self.grace_period_chrc)
            self.add_characteristic(self.hotspot_control_chrc)


    class GracePeriodCharacteristic(Characteristic):
        """Grace Period characteristic with write support for cancel."""

        def __init__(self, bus, index, service):
            super().__init__(
                bus, index, BLE_GRACE_PERIOD_UUID,
                ['read', 'write', 'notify'], service
            )
            self.on_cancel_from_app: Optional[Callable] = None
            self.value = dbus.Array([0x00, 0x00], signature='y')

        def WriteValue(self, value, options):
            self.value = value
            if len(value) > 0 and value[0] == 0x00:
                print("BLE: Cancel received from iOS app")
                if self.on_cancel_from_app:
                    self.on_cancel_from_app()


    class HotspotControlCharacteristic(Characteristic):
        """Hotspot control characteristic: iOS writes 0x01 to activate, 0x00 to deactivate."""

        def __init__(self, bus, index, service):
            super().__init__(
                bus, index, BLE_HOTSPOT_CONTROL_UUID,
                ['read', 'write', 'notify'], service
            )
            self.on_hotspot_request: Optional[Callable] = None
            self.value = dbus.Array([HOTSPOT_OFF], signature='y')

        def WriteValue(self, value, options):
            if len(value) == 0:
                return
            command = int(value[0])
            print(f"BLE: Hotspot control write received: 0x{command:02X}")
            if self.on_hotspot_request:
                self.on_hotspot_request(command)


    class Advertisement(dbus.service.Object):
        """BLE Advertisement object."""

        def __init__(self, bus, index):
            self.path = f'/org/bikebox/advertisement{index}'
            self.bus = bus
            self.ad_type = 'peripheral'
            self.service_uuids = [BLE_SERVICE_UUID]
            self.local_name = BLE_LOCAL_NAME
            self.include_tx_power = True
            dbus.service.Object.__init__(self, bus, self.path)

        def get_properties(self):
            return {
                LE_ADVERTISEMENT_IFACE: {
                    'Type': self.ad_type,
                    'ServiceUUIDs': dbus.Array(self.service_uuids, signature='s'),
                    'LocalName': dbus.String(self.local_name),
                    'IncludeTxPower': dbus.Boolean(self.include_tx_power),
                }
            }

        def get_path(self):
            return dbus.ObjectPath(self.path)

        @dbus.service.method(DBUS_PROP_IFACE, in_signature='s',
                             out_signature='a{sv}')
        def GetAll(self, interface):
            if interface != LE_ADVERTISEMENT_IFACE:
                raise dbus.exceptions.DBusException(
                    'org.freedesktop.DBus.Error.InvalidArgs')
            return self.get_properties()[LE_ADVERTISEMENT_IFACE]

        @dbus.service.method(LE_ADVERTISEMENT_IFACE, in_signature='',
                             out_signature='')
        def Release(self):
            print("BLE: Advertisement released")


class BLEServer:
    """
    High-level BLE server manager.

    Provides methods to send crash alerts, device status updates,
    and grace period countdown values. Runs the GLib main loop
    in a background thread.
    """

    def __init__(self) -> None:
        self._app = None
        self._adv = None
        self._agent = None
        self._mainloop = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        """Initialize and start the BLE GATT server + advertisement."""
        if not DBUS_AVAILABLE:
            print("BLE: dbus/gi not available. BLE disabled.")
            return

        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SystemBus()

        adapter = self._find_adapter(bus)
        if not adapter:
            print("BLE: No Bluetooth adapter found. BLE disabled.")
            return

        adapter_obj = bus.get_object(BLUEZ_SERVICE_NAME, adapter)
        adapter_props = dbus.Interface(adapter_obj, DBUS_PROP_IFACE)
        adapter_props.Set('org.bluez.Adapter1', 'Powered', dbus.Boolean(1))
        adapter_props.Set('org.bluez.Adapter1', 'Pairable', dbus.Boolean(1))
        adapter_props.Set('org.bluez.Adapter1', 'PairableTimeout', dbus.UInt32(0))
        adapter_props.Set('org.bluez.Adapter1', 'Discoverable', dbus.Boolean(1))
        adapter_props.Set('org.bluez.Adapter1', 'DiscoverableTimeout', dbus.UInt32(0))

        self._agent = PairingAgent(bus)
        agent_manager = dbus.Interface(
            bus.get_object(BLUEZ_SERVICE_NAME, '/org/bluez'),
            AGENT_MANAGER_IFACE
        )
        agent_manager.RegisterAgent(PairingAgent.AGENT_PATH, 'NoInputNoOutput')
        agent_manager.RequestDefaultAgent(PairingAgent.AGENT_PATH)
        print("BLE: Pairing agent registered (NoInputNoOutput / Just Works)")

        self._app = Application(bus)
        service_manager = dbus.Interface(
            bus.get_object(BLUEZ_SERVICE_NAME, adapter),
            GATT_MANAGER_IFACE
        )
        service_manager.RegisterApplication(
            self._app.get_path(), {},
            reply_handler=lambda: print("BLE: GATT application registered"),
            error_handler=lambda e: print(f"BLE: GATT registration failed: {e}")
        )

        self._adv = Advertisement(bus, 0)
        ad_manager = dbus.Interface(
            bus.get_object(BLUEZ_SERVICE_NAME, adapter),
            LE_ADVERTISING_MANAGER_IFACE
        )
        ad_manager.RegisterAdvertisement(
            self._adv.get_path(), {},
            reply_handler=lambda: print("BLE: Advertisement registered"),
            error_handler=lambda e: print(f"BLE: Advert registration failed: {e}")
        )

        self._mainloop = GLib.MainLoop()
        self._running = True
        self._thread = threading.Thread(
            target=self._mainloop.run,
            daemon=True,
            name='ble-mainloop'
        )
        self._thread.start()
        print(f"BLE: Server running as '{BLE_LOCAL_NAME}'")

    def stop(self) -> None:
        """Stop the BLE server."""
        self._running = False
        if self._mainloop:
            self._mainloop.quit()
        print("BLE: Server stopped")

    def send_crash_alert(
        self,
        alert_type: int,
        lat: float,
        lon: float,
        peak_g: float,
        tilt: float,
        timestamp: float,
        battery_pct: int,
        clip_available: int = 0,
    ) -> None:
        """Write crash alert payload to the Crash Alert characteristic.

        Payload is 18 bytes: the original 17 + 1 byte clip_available flag.
        Old iOS apps that check data.count >= 17 will simply ignore byte 18.
        """
        if not self._app:
            return

        peak_g_int = int(peak_g * 100)
        tilt_int = int(min(tilt, 180))
        ts_int = int(timestamp)
        bat = int(max(0, min(100, battery_pct)))
        clip = int(bool(clip_available))

        payload = struct.pack('<BffHBIBB',
            alert_type, lat, lon, peak_g_int, tilt_int, ts_int, bat, clip
        )

        service = self._app.services[0]
        service.crash_alert_chrc.send_notification(list(payload))
        print(f"BLE: Crash alert sent (type=0x{alert_type:02X}, "
              f"lat={lat:.6f}, lon={lon:.6f}, g={peak_g:.2f}, "
              f"clip={'yes' if clip else 'no'})")

    def send_device_status(
        self,
        device_state: int,
        battery_pct: int,
        gps_fix: bool,
        uptime_min: int,
    ) -> None:
        """Write device status to the Device Status characteristic."""
        if not self._app:
            return

        payload = struct.pack('<BBBH',
            device_state,
            int(max(0, min(100, battery_pct))),
            1 if gps_fix else 0,
            int(min(uptime_min, 65535))
        )

        service = self._app.services[0]
        service.device_status_chrc.send_notification(list(payload))

    def send_grace_period(self, grace_state: int, seconds_remaining: int) -> None:
        """Write grace period state to the Grace Period characteristic."""
        if not self._app:
            return

        payload = [grace_state, int(seconds_remaining)]
        service = self._app.services[0]
        service.grace_period_chrc.send_notification(payload)

    def send_hotspot_state(self, state: int) -> None:
        """Notify iOS of the current hotspot state."""
        if not self._app:
            return
        service = self._app.services[0]
        service.hotspot_control_chrc.send_notification([state])

    def set_cancel_callback(self, callback: Callable) -> None:
        """Register a callback for when the iOS app sends a cancel command."""
        if self._app and self._app.services:
            service = self._app.services[0]
            service.grace_period_chrc.on_cancel_from_app = callback

    def set_hotspot_callback(self, callback: Callable) -> None:
        """Register a callback for when the iOS app sends a hotspot command."""
        if self._app and self._app.services:
            service = self._app.services[0]
            service.hotspot_control_chrc.on_hotspot_request = callback

    def _find_adapter(self, bus) -> Optional[str]:
        """Find the first Bluetooth adapter on D-Bus."""
        remote_om = dbus.Interface(
            bus.get_object(BLUEZ_SERVICE_NAME, '/'),
            DBUS_OM_IFACE
        )
        objects = remote_om.GetManagedObjects()
        for path, interfaces in objects.items():
            if GATT_MANAGER_IFACE in interfaces:
                return path
        return None
