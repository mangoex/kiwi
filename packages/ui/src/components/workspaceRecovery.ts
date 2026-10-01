// Only post-receipt validation failures prove that an uncertain command did not commit.
export function isWorkspaceRejection(status: number | undefined, code: string, recovering: boolean, operation: 'purchase' | 'copy'): boolean {
  if (!recovering) return [400, 403, 409, 413, 422].includes(status || 0) && !code.includes('idempotency') && !code.includes('identity_conflict');
  if (status !== 409) return false;
  const purchase = ['purchase_preview_changed', 'invalid_purchase_line', 'purchase_presentation_not_found', 'purchase_supplier_or_branch_not_found', 'supplier_not_enabled_for_branch', 'purchase_document_date_invalid', 'workspace_payload_invalid', 'purchase_lines_required', 'purchase_folio_required', 'invalid_purchase_document_type', 'cash_purchase_payment_mismatch', 'freight_cost_policy_required', 'presentation_reference_not_found', 'presentation_unit_mismatch', 'invalid_purchase_presentation'];
  const copy = ['modifier_copy_source_version_conflict', 'modifier_configuration_version_conflict', 'modifier_component_recipe_required', 'modifier_component_self_reference', 'modifier_component_out_of_scope', 'modifier_component_station_mismatch', 'modifier_component_nested'];
  return (operation === 'purchase' ? purchase : copy).includes(code);
}
