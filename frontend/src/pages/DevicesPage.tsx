import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Router, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { devicesApi } from "../api/devices";
import { ApiError } from "../api/client";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { DeviceForm } from "../components/DeviceForm";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { Modal } from "../components/Modal";
import { StatusBadge } from "../components/StatusBadge";
import { useToast } from "../components/useToast";
import { useAuth } from "../auth/useAuth";
import type { Device, DeviceCreate } from "../types/device";
import { hasAtLeastRole } from "../types/auth";

export function DevicesPage() {
  const { user } = useAuth();
  const canManage = hasAtLeastRole(user?.role, "operator");
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();

  const [search, setSearch] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Device | null>(null);
  const [deleting, setDeleting] = useState<Device | null>(null);

  const devicesQuery = useQuery({ queryKey: ["devices"], queryFn: () => devicesApi.list() });

  const invalidateDevices = () => queryClient.invalidateQueries({ queryKey: ["devices"] });

  const createMutation = useMutation({
    mutationFn: devicesApi.create,
    onSuccess: () => {
      invalidateDevices();
      setFormOpen(false);
      showSuccess("Device created.");
    },
    onError: (err) => showError(err instanceof ApiError ? err.detail : "Failed to create device."),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, values }: { id: number; values: DeviceCreate }) => devicesApi.update(id, values),
    onSuccess: () => {
      invalidateDevices();
      setEditing(null);
      showSuccess("Device updated.");
    },
    onError: (err) => showError(err instanceof ApiError ? err.detail : "Failed to update device."),
  });

  const deleteMutation = useMutation({
    mutationFn: devicesApi.remove,
    onSuccess: () => {
      invalidateDevices();
      setDeleting(null);
      showSuccess("Device deleted.");
    },
    onError: (err) => {
      showError(err instanceof ApiError ? err.detail : "Failed to delete device.");
      setDeleting(null);
    },
  });

  if (devicesQuery.isLoading) return <LoadingSpinner label="Loading devices..." />;
  if (devicesQuery.isError) return <ErrorState error={devicesQuery.error} onRetry={() => devicesQuery.refetch()} />;

  const devices = (devicesQuery.data ?? []).filter((device) => {
    const query = search.trim().toLowerCase();
    if (!query) return true;
    return (
      device.hostname.toLowerCase().includes(query) ||
      device.ip_address.toLowerCase().includes(query) ||
      device.vendor.toLowerCase().includes(query)
    );
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-noc-text">Devices</h1>
          <p className="text-sm text-noc-text-muted">{devicesQuery.data?.length ?? 0} devices in inventory</p>
        </div>
        {canManage && (
          <button
            type="button"
            onClick={() => setFormOpen(true)}
            className="flex items-center gap-1.5 rounded-md bg-status-up px-3 py-2 text-sm font-medium text-white hover:bg-status-up/90"
          >
            <Plus className="h-4 w-4" /> Add device
          </button>
        )}
      </div>

      <input
        placeholder="Search by hostname, IP, or vendor..."
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        className="w-full max-w-sm rounded-md border border-noc-border bg-noc-surface px-3 py-2 text-sm text-noc-text outline-none focus:border-status-up"
      />

      {devices.length === 0 ? (
        <EmptyState
          icon={Router}
          title="No devices found"
          description={search ? "Try a different search." : "Add your first device to get started."}
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-noc-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-noc-surface text-noc-text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Hostname</th>
                <th className="px-3 py-2 font-medium">IP address</th>
                <th className="px-3 py-2 font-medium">Vendor</th>
                <th className="px-3 py-2 font-medium">Type</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-noc-border">
              {devices.map((device) => (
                <tr key={device.id} className="bg-noc-surface hover:bg-noc-surface-raised">
                  <td className="px-3 py-2">
                    <Link to={`/devices/${device.id}`} className="text-status-up hover:underline">
                      {device.hostname}
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-noc-text">{device.ip_address}</td>
                  <td className="px-3 py-2 text-noc-text">{device.vendor}</td>
                  <td className="px-3 py-2 capitalize text-noc-text">{device.device_type.replace("_", " ")}</td>
                  <td className="px-3 py-2">
                    <StatusBadge status={device.status} />
                  </td>
                  <td className="px-3 py-2">
                    {canManage && (
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          aria-label={`Edit ${device.hostname}`}
                          onClick={() => setEditing(device)}
                          className="text-noc-text-muted hover:text-status-up"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          aria-label={`Delete ${device.hostname}`}
                          onClick={() => setDeleting(device)}
                          className="text-noc-text-muted hover:text-status-down"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={formOpen} title="Add device" onClose={() => setFormOpen(false)}>
        <DeviceForm
          submitLabel="Create"
          busy={createMutation.isPending}
          onCancel={() => setFormOpen(false)}
          onSubmit={(values) => createMutation.mutate(values)}
        />
      </Modal>

      <Modal open={editing !== null} title={`Edit ${editing?.hostname}`} onClose={() => setEditing(null)}>
        {editing && (
          <DeviceForm
            initial={editing}
            submitLabel="Save changes"
            busy={updateMutation.isPending}
            onCancel={() => setEditing(null)}
            onSubmit={(values) => updateMutation.mutate({ id: editing.id, values })}
          />
        )}
      </Modal>

      <ConfirmDialog
        open={deleting !== null}
        title="Delete device?"
        description={`This permanently deletes "${deleting?.hostname}" and all of its health, interface, and backup history. This can't be undone.`}
        confirmLabel="Delete"
        danger
        busy={deleteMutation.isPending}
        onCancel={() => setDeleting(null)}
        onConfirm={() => deleting && deleteMutation.mutate(deleting.id)}
      />
    </div>
  );
}
