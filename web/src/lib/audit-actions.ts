import type { TranslationKey } from "@/lib/i18n";

/** Shared labels for audit actions (spec #47). */
export const AUDIT_ACTION_LABELS: Record<string, TranslationKey> = {
  register: "audit.action.register",
  login: "audit.action.login",
  logout: "audit.action.logout",
  login_failed: "audit.action.login_failed",
  password_change: "audit.action.password_change",
  username_change: "audit.action.username_change",
  account_change: "audit.action.account_change",
  account_delete: "audit.action.account_delete",
  create_record: "audit.action.create_record",
  update_record: "audit.action.update_record",
  delete_record: "audit.action.delete_record",
  import: "audit.action.import",
  export: "audit.action.export",
  upload_attachment: "audit.action.upload_attachment",
  delete_attachment: "audit.action.delete_attachment",
  ai_action: "audit.action.ai_action",
  admin_bootstrap: "audit.action.admin_bootstrap",
  admin_update_user: "audit.action.admin_update_user",
};
