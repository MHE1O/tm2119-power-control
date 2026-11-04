import Gio from 'gi://Gio';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const OBJECT_PATH = '/org/tm2119/PowerProfile';
const INTERFACE_XML = `
<node>
  <interface name="org.tm2119.PowerProfile">
    <method name="ShowProfile">
      <arg type="s" name="profile" direction="in"/>
      <arg type="s" name="source" direction="in"/>
    </method>
  </interface>
</node>`;

const PROFILES = {
  'power-saver': ['Power Saver (Eco)', 'power-profile-power-saver-symbolic'],
  'balanced': ['Balanced', 'power-profile-balanced-symbolic'],
  'performance': ['Performance (Turbo)', 'power-profile-performance-symbolic'],
};

export default class Tm2119PowerOsdExtension extends Extension {
  enable() {
    this._exported = Gio.DBusExportedObject.wrapJSObject(INTERFACE_XML, {
      ShowProfile: (profile, _source) => this._showProfile(profile),
    });
    this._exported.export(Gio.DBus.session, OBJECT_PATH);
  }

  _showProfile(profile) {
    const info = PROFILES[profile];
    if (!info)
      return;

    const [title, iconName] = info;
    const icon = new Gio.ThemedIcon({name: iconName});
    const monitor = Main.layoutManager.primaryIndex;
    const osdWindowManager = Main.osdWindowManager;
    if (typeof osdWindowManager.showOne === 'function')
      osdWindowManager.showOne(monitor, icon, title, null);
    else
      osdWindowManager.show(monitor, icon, title, null);
  }

  disable() {
    this._exported?.unexport();
    this._exported = null;
  }
}
