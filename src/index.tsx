import {
  ButtonItem,
  Field,
  PanelSection,
  PanelSectionRow,
  ServerAPI,
  SliderField,
  SteamSpinner,
  TextField,
  definePlugin
} from "decky-frontend-lib";
import { useEffect, useMemo, useRef, useState } from "react";

type SecretMeta = {
  id: string;
  name: string;
  created_at: number;
};

type SecretValue = {
  id: string;
  name: string;
  value: string;
};

type VaultStatus = {
  vault_backend: "gopass" | "local";
  clipboard_timeout: number;
  local_status: {
    password_required: boolean;
    locked: boolean;
  };
};

const formatDate = (timestamp: number) =>
  new Date(timestamp * 1000).toLocaleString();

const SecretsView = ({ serverAPI }: { serverAPI: ServerAPI }) => {
  const [secrets, setSecrets] = useState<SecretMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  const [clipboardTimeout, setClipboardTimeout] = useState(20);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState("");
  const [vaultBackend, setVaultBackend] = useState<"gopass" | "local">("gopass");
  const [localLocked, setLocalLocked] = useState(false);
  const [localPasswordRequired, setLocalPasswordRequired] = useState(false);
  const [localPassword, setLocalPassword] = useState("");
  const timerRef = useRef<number | null>(null);
  const timeoutSaveRef = useRef<number | null>(null);

  const filteredSecrets = useMemo(() => {
    const term = search.trim().toLowerCase();
    const sorted = [...secrets].sort((a, b) => b.created_at - a.created_at);
    if (!term) return sorted;
    return sorted.filter((secret) => secret.name.toLowerCase().includes(term));
  }, [secrets, search]);

  const backendLocked = vaultBackend === "local" && localLocked;

  useEffect(() => {
    const bootstrap = async () => {
      await refreshSecrets();
      await loadStatus();
      setLoading(false);
    };
    bootstrap();
    return () => {
      if (timerRef.current) {
        window.clearTimeout(timerRef.current);
      }
      if (timeoutSaveRef.current) {
        window.clearTimeout(timeoutSaveRef.current);
      }
    };
  }, []);

  const refreshSecrets = async () => {
    const res = await serverAPI.callPluginMethod<{}, SecretMeta[]>("list_secrets", {});
    if (res.success && res.result) {
      setSecrets(res.result);
    }
  };

  const loadStatus = async () => {
    const res = await serverAPI.callPluginMethod<{}, VaultStatus>("get_status", {});
    if (res.success && res.result) {
      setClipboardTimeout(res.result.clipboard_timeout);
      setVaultBackend(res.result.vault_backend);
      setLocalLocked(res.result.local_status.locked);
      setLocalPasswordRequired(res.result.local_status.password_required);
    }
  };

  const handleAdd = async () => {
    if (backendLocked) {
      serverAPI.toaster.toast({ title: "Vault locked", body: "Unlock the local vault to add secrets." });
      return;
    }
    if (!name.trim() || !value.trim()) return;
    setSaving(true);
    const res = await serverAPI.callPluginMethod<{ name: string; value: string }, SecretMeta>(
      "add_secret",
      { name: name.trim(), value }
    );
      setSaving(false);
      if (res.success) {
        setName("");
        setValue("");
        await refreshSecrets();
        serverAPI.toaster.toast({
          title: "Secret stored",
          body: "Saved to gopass. Value will not be shown again."
        });
      } else {
        serverAPI.toaster.toast({ title: "Save failed", body: "Could not store secret." });
      }
  };

  const handleDelete = async (secretId: string, secretName: string) => {
    if (backendLocked) {
      serverAPI.toaster.toast({ title: "Vault locked", body: "Unlock the local vault to delete secrets." });
      return;
    }
    const confirmed = window.confirm(`Delete "${secretName}"? This cannot be undone.`);
    if (!confirmed) return;
    const res = await serverAPI.callPluginMethod<{ secret_id: string }, boolean>("delete_secret", {
      secret_id: secretId
    });
    if (res.success && res.result) {
      await refreshSecrets();
      serverAPI.toaster.toast({ title: "Secret removed", body: "Entry deleted." });
    } else {
      serverAPI.toaster.toast({ title: "Remove failed", body: "Could not delete secret." });
    }
  };

  const clearClipboard = async () => {
    try {
      await navigator.clipboard.writeText("");
      serverAPI.toaster.toast({ title: "Clipboard cleared", body: "Secret removed from pasteboard." });
    } catch (err) {
      console.error("Failed to clear clipboard", err);
    }
  };

  const handleCopy = async (secretId: string) => {
    if (backendLocked) {
      serverAPI.toaster.toast({ title: "Vault locked", body: "Unlock the local vault to copy secrets." });
      return;
    }
    const res = await serverAPI.callPluginMethod<{ secret_id: string }, SecretValue | null>(
      "get_secret",
      { secret_id: secretId }
    );
    if (!res.success || !res.result) {
      serverAPI.toaster.toast({ title: "Unable to decrypt", body: "Could not retrieve secret." });
      return;
    }

    try {
      await navigator.clipboard.writeText(res.result.value);
      serverAPI.toaster.toast({
        title: "Copied",
        body: `Placed "${res.result.name}" onto the clipboard for ${clipboardTimeout}s.`
      });
      if (timerRef.current) {
        window.clearTimeout(timerRef.current);
      }
      timerRef.current = window.setTimeout(clearClipboard, clipboardTimeout * 1000);
    } catch (err) {
      console.error("Failed to copy secret", err);
      serverAPI.toaster.toast({ title: "Clipboard error", body: "Could not write to the clipboard." });
    } finally {
      res.result.value = "";
    }
  };

  const handleTimeoutChange = (val: number) => {
    setClipboardTimeout(val);
    if (timeoutSaveRef.current) {
      window.clearTimeout(timeoutSaveRef.current);
    }
    timeoutSaveRef.current = window.setTimeout(async () => {
      const res = await serverAPI.callPluginMethod<{ seconds: number }, number>("set_clipboard_timeout", {
        seconds: val
      });
      if (!res.success) {
        serverAPI.toaster.toast({ title: "Save failed", body: "Could not update timeout." });
      }
    }, 350);
  };

  const handleBackendChange = async (target: "gopass" | "local") => {
    const res = await serverAPI.callPluginMethod<{ backend: string }, VaultStatus>("set_vault_backend", {
      backend: target
    });
    if (res.success && res.result) {
      setVaultBackend(target);
      setLocalLocked(res.result.local_status.locked);
      setLocalPasswordRequired(res.result.local_status.password_required);
      await refreshSecrets();
      serverAPI.toaster.toast({
        title: "Backend updated",
        body: target === "gopass" ? "Using gopass for storage." : "Using local encrypted vault."
      });
    } else {
      serverAPI.toaster.toast({ title: "Backend change failed", body: "Could not update storage backend." });
    }
  };

  const handleLocalPasswordSave = async () => {
    const res = await serverAPI.callPluginMethod<{ password: string }, VaultStatus>("configure_local_vault", {
      password: localPassword
    });
    if (res.success && res.result) {
      setLocalLocked(res.result.local_status.locked);
      setLocalPasswordRequired(res.result.local_status.password_required);
      serverAPI.toaster.toast({
        title: "Local vault updated",
        body: localPassword ? "Unlock password set." : "Password removed."
      });
    } else {
      serverAPI.toaster.toast({ title: "Update failed", body: "Could not update local vault settings." });
    }
  };

  const handleLocalUnlock = async () => {
    const res = await serverAPI.callPluginMethod<{ password: string }, VaultStatus>("unlock_local_vault", {
      password: localPassword
    });
    if (res.success && res.result) {
      setLocalLocked(res.result.local_status.locked);
      serverAPI.toaster.toast({
        title: res.result.local_status.locked ? "Unlock failed" : "Vault unlocked",
        body: res.result.local_status.locked ? "Password incorrect." : "Local vault ready."
      });
      if (!res.result.local_status.locked) {
        await refreshSecrets();
      }
    } else {
      serverAPI.toaster.toast({ title: "Unlock failed", body: "Could not unlock local vault." });
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      <PanelSection title="Vault backend">
        <PanelSectionRow>
          <Field
            label="Current backend"
            description={
              vaultBackend === "gopass"
                ? "Using gopass for storage."
                : localPasswordRequired
                ? localLocked
                  ? "Local vault locked (unlock required)."
                  : "Local vault unlocked (password protected)."
                : "Local vault unlocked (no password)."
            }
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            onClick={() => handleBackendChange("gopass")}
            disabled={vaultBackend === "gopass"}
          >
            Use gopass backend
          </ButtonItem>
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            onClick={() => handleBackendChange("local")}
            disabled={vaultBackend === "local"}
          >
            Use local encrypted backend
          </ButtonItem>
        </PanelSectionRow>
        <PanelSectionRow>
          <TextField
            label="Local vault password (optional)"
            value={localPassword}
            onChange={(e: any) => setLocalPassword(e?.target?.value ?? "")}
            placeholder="Set or enter password"
            type="password"
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={handleLocalPasswordSave} disabled={vaultBackend !== "local"}>
            {localPassword ? "Set/Update password" : "Remove password"}
          </ButtonItem>
        </PanelSectionRow>
        {localPasswordRequired && (
          <PanelSectionRow>
            <ButtonItem layout="below" onClick={handleLocalUnlock} disabled={vaultBackend !== "local"}>
              Unlock local vault
            </ButtonItem>
          </PanelSectionRow>
        )}
      </PanelSection>

      <PanelSection title="Add a secret">
        <PanelSectionRow>
          <TextField
            label="Secret name"
            value={name}
            onChange={(e: any) => setName(e?.target?.value ?? "")}
            placeholder="e.g. API token"
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <TextField
            label="Secret value"
            value={value}
            onChange={(e: any) => setValue(e?.target?.value ?? "")}
            placeholder="Value is only used once when saving"
            type="password"
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem
            disabled={saving || backendLocked || !name.trim() || !value.trim()}
            onClick={handleAdd}
            layout="below"
          >
            {saving ? "Saving..." : "Encrypt and store"}
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>

      <PanelSection title="Clipboard">
        <PanelSectionRow>
          <SliderField
            label="Auto-clear clipboard after (seconds)"
            value={clipboardTimeout}
            step={1}
            min={3}
            max={180}
            showValue={true}
            onChange={(val: number) => handleTimeoutChange(val)}
          />
        </PanelSectionRow>
      </PanelSection>

      <PanelSection title="Stored secrets">
        <PanelSectionRow>
          <TextField
            label="Search"
            value={search}
            onChange={(e: any) => setSearch(e?.target?.value ?? "")}
            placeholder="Filter by name"
          />
        </PanelSectionRow>
        {loading ? (
          <PanelSectionRow>
            <SteamSpinner />
          </PanelSectionRow>
        ) : filteredSecrets.length === 0 ? (
          <PanelSectionRow>
            <Field label="No secrets yet" description="Add one above to get started." />
          </PanelSectionRow>
        ) : (
          filteredSecrets.map((secret) => (
            <PanelSectionRow key={secret.id}>
              <ButtonItem onClick={() => handleCopy(secret.id)} layout="below" disabled={backendLocked}>
                <div style={{ display: "flex", justifyContent: "space-between", width: "100%" }}>
                  <div>
                    <div>{secret.name}</div>
                    <div style={{ opacity: 0.6, fontSize: "12px" }}>Saved {formatDate(secret.created_at)}</div>
                  </div>
                  <div
                    onClick={(event) => {
                      event.stopPropagation();
                      handleDelete(secret.id, secret.name);
                    }}
                    style={{
                      color: "var(--gpColor-Red)",
                      cursor: "pointer",
                      fontWeight: 700,
                      alignSelf: "center"
                    }}
                  >
                    Delete
                  </div>
                </div>
              </ButtonItem>
            </PanelSectionRow>
          ))
        )}
      </PanelSection>
    </div>
  );
};

export default definePlugin((serverAPI: ServerAPI) => {
  return {
    title: "SecretsPaste",
    content: <SecretsView serverAPI={serverAPI} />,
    icon: "lock"
  };
});
