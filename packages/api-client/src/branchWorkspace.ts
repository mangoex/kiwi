/** Central workspace secrets live only in this document's memory (SDD 58.2). */
export interface BranchWorkspaceProfile {
  organization_id?: string;
  user: { id: string };
  scope: { authorization_version?: number; allowed_branch_ids: string[] };
  active_branch: { id: string } | null;
  branch_selection_required?: boolean;
  branch_workspace_context_id?: string | null;
  branch_workspace_context?: string | null;
  branch_workspace_secret_version?: number | null;
  branch_workspace_state?: string | null;
  branch_context_reissue_required?: boolean;
}

export interface BranchWorkspaceRequest {
  readonly generation: number;
  readonly credential: string;
}

interface WorkspaceIdentity {
  organization: string;
  actor: string;
  branch: string;
  context: string;
  authorityVersion: number;
  secretVersion: number;
}

let generation = 0;
let credential: string | null = null;
let installed: (WorkspaceIdentity & { secret: string }) | null = null;
const greatestVersions = new Map<string, number>();

export function clearBranchWorkspace(): void {
  generation++;
  credential = null;
  installed = null;
  greatestVersions.clear();
}

export function beginBranchWorkspaceRequest(currentCredential: string): BranchWorkspaceRequest {
  if (credential !== currentCredential) clearBranchWorkspace();
  credential = currentCredential;
  return { generation: ++generation, credential: currentCredential };
}

export function isCurrentBranchWorkspaceRequest(
  request: BranchWorkspaceRequest,
  currentCredential: string | null,
): boolean {
  return Boolean(currentCredential)
    && request.generation === generation
    && request.credential === currentCredential
    && credential === currentCredential;
}

function identity(profile: BranchWorkspaceProfile): WorkspaceIdentity | null {
  const authorityVersion = profile.scope.authorization_version;
  const secretVersion = profile.branch_workspace_secret_version;
  if (!profile.organization_id || !profile.user.id || !profile.active_branch?.id
    || !profile.scope.allowed_branch_ids.includes(profile.active_branch.id)
    || !profile.branch_workspace_context_id || profile.branch_workspace_state !== 'active'
    || !Number.isSafeInteger(authorityVersion) || !authorityVersion || authorityVersion < 1
    || !Number.isSafeInteger(secretVersion) || !secretVersion || secretVersion < 1) return null;
  return {
    organization: profile.organization_id,
    actor: profile.user.id,
    branch: profile.active_branch.id,
    context: profile.branch_workspace_context_id,
    authorityVersion,
    secretVersion,
  };
}

export function hydrateBranchWorkspace(
  profile: BranchWorkspaceProfile,
  request: BranchWorkspaceRequest,
  currentCredential: string | null,
): boolean {
  if (!isCurrentBranchWorkspaceRequest(request, currentCredential)) return false;
  const next = identity(profile);
  if (!next || !installed || Object.entries(next).some(
    ([key, value]) => installed?.[key as keyof WorkspaceIdentity] !== value,
  )) {
    installed = null;
    return false;
  }
  return true;
}

export function installBranchWorkspace(
  profile: BranchWorkspaceProfile,
  request: BranchWorkspaceRequest,
  currentCredential: string | null,
): boolean {
  if (!isCurrentBranchWorkspaceRequest(request, currentCredential)) return false;
  const next = identity(profile);
  const secret = profile.branch_workspace_context;
  if (!next || typeof secret !== 'string' || secret.length < 32 || secret.length > 128
    || next.secretVersion <= (greatestVersions.get(next.context) ?? 0)) return false;
  greatestVersions.set(next.context, next.secretVersion);
  installed = { ...next, secret };
  return true;
}

/** Never use a form-saved header or a context confirmed under a previous bearer. */
export function branchWorkspaceSecret(currentCredential: string | null): string | null {
  if (credential !== currentCredential) {
    clearBranchWorkspace();
    return null;
  }
  return installed?.secret ?? null;
}

/** Hydration and reissue use a single response fence before publishing any operational UI. */
export async function ensureBranchWorkspace<T extends BranchWorkspaceProfile>(
  profile: T,
  request: BranchWorkspaceRequest,
  currentCredential: () => string | null,
  issue: (body: {context_id: string | null; expected_authorization_version: number}) => Promise<T>,
): Promise<T> {
  if (!isCurrentBranchWorkspaceRequest(request, currentCredential())) {
    throw new Error('branch_workspace_response_superseded');
  }
  const usable = hydrateBranchWorkspace(profile, request, currentCredential());
  if (profile.branch_context_reissue_required === undefined || !profile.active_branch || usable) {
    return { ...profile, branch_workspace_context: null };
  }
  const version = profile.scope.authorization_version;
  if (!Number.isSafeInteger(version) || !version || version < 1
    || (profile.branch_workspace_state && profile.branch_workspace_state !== 'active')) {
    throw new Error('branch_workspace_recovery_required');
  }
  const issued = await issue({
    context_id: profile.branch_workspace_context_id ?? null,
    expected_authorization_version: version,
  });
  if (issued.organization_id !== profile.organization_id || issued.user.id !== profile.user.id
    || issued.active_branch?.id !== profile.active_branch.id
    || issued.scope.authorization_version !== version
    || (profile.branch_workspace_context_id
      && issued.branch_workspace_context_id !== profile.branch_workspace_context_id)
    || !installBranchWorkspace(issued, request, currentCredential())) {
    throw new Error('branch_workspace_response_superseded');
  }
  return { ...issued, branch_workspace_context: null };
}

export interface BranchSelectionIntent {
  organization: string;
  actor: string;
  targetBranchId: string;
  authorizationVersion: number;
  idempotencyKey: string;
}

const SELECTION_INTENT_PREFIX = 'pos_branch_selection_intent_v2:';
function selectionKey(profile: BranchWorkspaceProfile): string {
  if (!profile.organization_id || !profile.user.id) throw new Error('branch_selection_authority_required');
  return `${SELECTION_INTENT_PREFIX}${profile.organization_id}:${profile.user.id}`;
}

export function readBranchSelectionIntent(profile: BranchWorkspaceProfile): BranchSelectionIntent | null {
  const key = selectionKey(profile);
  const version = profile.scope.authorization_version;
  if (!Number.isSafeInteger(version) || !version || version < 1) {
    throw new Error('branch_selection_authority_required');
  }
  if (sessionStorage.getItem('pos_branch_selection_intent_v1')) {
    throw new Error('branch_selection_legacy_intent_requires_review');
  }
  const stored = sessionStorage.getItem(key);
  if (stored) {
    let intent: BranchSelectionIntent;
    try { intent = JSON.parse(stored) as BranchSelectionIntent; }
    catch { throw new Error('branch_selection_intent_invalid'); }
    if (!intent || Object.keys(intent).sort().join(',') !== 'actor,authorizationVersion,idempotencyKey,organization,targetBranchId'
      || intent.organization !== profile.organization_id || intent.actor !== profile.user.id
      || !Number.isSafeInteger(intent.authorizationVersion) || intent.authorizationVersion < 1
      || typeof intent.idempotencyKey !== 'string' || intent.idempotencyKey.length < 12
      || typeof intent.targetBranchId !== 'string') throw new Error('branch_selection_intent_invalid');
    if (intent.authorizationVersion !== version) throw new Error('branch_selection_intent_authority_changed');
    if (!profile.scope.allowed_branch_ids.includes(intent.targetBranchId)) throw new Error('branch_selection_intent_authority_changed');
    return intent;
  }
  return null;
}

export function branchSelectionIntent(
  profile: BranchWorkspaceProfile,
  targetBranchId: string,
): BranchSelectionIntent {
  if (!profile.scope.allowed_branch_ids.includes(targetBranchId)) throw new Error('branch_selection_authority_required');
  const existing = readBranchSelectionIntent(profile);
  if (existing) {
    if (existing.targetBranchId !== targetBranchId) throw new Error('branch_selection_uncertain_intent');
    return existing;
  }
  const key = selectionKey(profile);
  const intent: BranchSelectionIntent = {
    organization: profile.organization_id!, actor: profile.user.id,
    targetBranchId, authorizationVersion: profile.scope.authorization_version!, idempotencyKey: crypto.randomUUID(),
  };
  sessionStorage.setItem(key, JSON.stringify(intent));
  if (sessionStorage.getItem(key) !== JSON.stringify(intent)) throw new Error('branch_selection_intent_not_saved');
  return intent;
}

export function clearBranchSelectionIntent(profile: BranchWorkspaceProfile): void {
  sessionStorage.removeItem(selectionKey(profile));
}
