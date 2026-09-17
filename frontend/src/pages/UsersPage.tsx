import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { authApi } from "../api/auth";
import { ApiError } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { useToast } from "../components/useToast";
import { useAuth } from "../auth/useAuth";
import type { User, UserRole } from "../types/auth";

const ROLES: UserRole[] = ["viewer", "operator", "admin"];

export function UsersPage() {
  const { user: currentUser } = useAuth();
  const queryClient = useQueryClient();
  const { showSuccess, showError } = useToast();
  const [pendingId, setPendingId] = useState<number | null>(null);

  const usersQuery = useQuery({ queryKey: ["users"], queryFn: authApi.listUsers });

  const updateMutation = useMutation({
    mutationFn: ({ id, ...update }: { id: number; role?: UserRole; is_active?: boolean }) =>
      authApi.updateUser(id, update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      showSuccess("User updated.");
    },
    onError: (err) => showError(err instanceof ApiError ? err.detail : "Failed to update user."),
    onSettled: () => setPendingId(null),
  });

  function handleRoleChange(user: User, role: UserRole) {
    setPendingId(user.id);
    updateMutation.mutate({ id: user.id, role });
  }

  function handleToggleActive(user: User) {
    setPendingId(user.id);
    updateMutation.mutate({ id: user.id, is_active: !user.is_active });
  }

  if (usersQuery.isLoading) return <LoadingSpinner label="Loading users..." />;
  if (usersQuery.isError) return <ErrorState error={usersQuery.error} onRetry={() => usersQuery.refetch()} />;

  const users = usersQuery.data ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-semibold text-noc-text">Users</h1>
        <p className="text-sm text-noc-text-muted">Manage accounts and roles. New accounts are added via the API's registration endpoint.</p>
      </div>

      {users.length === 0 ? (
        <EmptyState title="No users found" />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-noc-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-noc-surface text-noc-text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Username</th>
                <th className="px-3 py-2 font-medium">Email</th>
                <th className="px-3 py-2 font-medium">Role</th>
                <th className="px-3 py-2 font-medium">Active</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-noc-border">
              {users.map((user) => {
                const isSelf = user.id === currentUser?.id;
                const busy = updateMutation.isPending && pendingId === user.id;
                return (
                  <tr key={user.id} className="bg-noc-surface">
                    <td className="px-3 py-2 text-noc-text">
                      {user.username}
                      {isSelf && <span className="ml-1 text-xs text-noc-text-muted">(you)</span>}
                    </td>
                    <td className="px-3 py-2 text-noc-text-muted">{user.email}</td>
                    <td className="px-3 py-2">
                      <select
                        value={user.role}
                        disabled={isSelf || busy}
                        onChange={(event) => handleRoleChange(user, event.target.value as UserRole)}
                        className="rounded-md border border-noc-border bg-noc-bg px-2 py-1 text-sm text-noc-text disabled:opacity-50"
                      >
                        {ROLES.map((role) => (
                          <option key={role} value={role}>
                            {role}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-2">
                      <button
                        type="button"
                        disabled={isSelf || busy}
                        onClick={() => handleToggleActive(user)}
                        className={`rounded-full border px-2 py-0.5 text-xs disabled:opacity-50 ${
                          user.is_active
                            ? "border-status-up/30 bg-status-up/15 text-status-up"
                            : "border-status-down/30 bg-status-down/15 text-status-down"
                        }`}
                      >
                        {user.is_active ? "Active" : "Deactivated"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
