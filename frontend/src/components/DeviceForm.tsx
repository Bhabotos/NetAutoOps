import { useState, type FormEvent } from "react";
import { DEVICE_STATUSES, DEVICE_TYPES, type Device, type DeviceCreate } from "../types/device";

const inputClass =
  "w-full rounded-md border border-noc-border bg-noc-bg px-3 py-2 text-sm text-noc-text outline-none focus:border-status-up";
const labelClass = "mb-1 block text-sm text-noc-text-muted";

export function DeviceForm({
  initial,
  submitLabel,
  busy,
  onSubmit,
  onCancel,
}: {
  initial?: Device;
  submitLabel: string;
  busy: boolean;
  onSubmit: (values: DeviceCreate) => void;
  onCancel: () => void;
}) {
  const [values, setValues] = useState<DeviceCreate>({
    hostname: initial?.hostname ?? "",
    ip_address: initial?.ip_address ?? "",
    vendor: initial?.vendor ?? "",
    device_type: initial?.device_type ?? "router",
    username: initial?.username ?? "",
    status: initial?.status ?? "unknown",
    description: initial?.description ?? "",
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onSubmit(values);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className={labelClass} htmlFor="hostname">
            Hostname
          </label>
          <input
            id="hostname"
            required
            className={inputClass}
            value={values.hostname}
            onChange={(event) => setValues({ ...values, hostname: event.target.value })}
          />
        </div>
        <div>
          <label className={labelClass} htmlFor="ip_address">
            IP address
          </label>
          <input
            id="ip_address"
            required
            className={inputClass}
            value={values.ip_address}
            onChange={(event) => setValues({ ...values, ip_address: event.target.value })}
          />
        </div>
        <div>
          <label className={labelClass} htmlFor="vendor">
            Vendor
          </label>
          <input
            id="vendor"
            required
            className={inputClass}
            value={values.vendor}
            onChange={(event) => setValues({ ...values, vendor: event.target.value })}
          />
        </div>
        <div>
          <label className={labelClass} htmlFor="device_type">
            Device type
          </label>
          <select
            id="device_type"
            className={inputClass}
            value={values.device_type}
            onChange={(event) => setValues({ ...values, device_type: event.target.value as DeviceCreate["device_type"] })}
          >
            {DEVICE_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelClass} htmlFor="username">
            SSH username
          </label>
          <input
            id="username"
            required
            className={inputClass}
            value={values.username}
            onChange={(event) => setValues({ ...values, username: event.target.value })}
          />
        </div>
        <div>
          <label className={labelClass} htmlFor="status">
            Status
          </label>
          <select
            id="status"
            className={inputClass}
            value={values.status}
            onChange={(event) => setValues({ ...values, status: event.target.value as DeviceCreate["status"] })}
          >
            {DEVICE_STATUSES.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div>
        <label className={labelClass} htmlFor="description">
          Description
        </label>
        <input
          id="description"
          className={inputClass}
          value={values.description ?? ""}
          onChange={(event) => setValues({ ...values, description: event.target.value })}
        />
      </div>
      <p className="text-xs text-noc-text-muted">
        The SSH password is never set here -- it comes only from the backend's{" "}
        <code>DEVICE_SSH_PASSWORD</code> environment variable and is shared by every device.
      </p>
      <div className="mt-2 flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-noc-border px-3 py-1.5 text-sm text-noc-text hover:bg-noc-surface"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-status-up px-3 py-1.5 text-sm font-medium text-white hover:bg-status-up/90 disabled:opacity-50"
        >
          {busy ? "Saving..." : submitLabel}
        </button>
      </div>
    </form>
  );
}
