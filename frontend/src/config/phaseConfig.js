export const phaseConfig = {
  1: { showInviteLink: false, canSaveDraft: true, canAdvance: true, collaborativeAutoSave: false },
  2: { showInviteLink: true, canSaveDraft: false, canAdvance: true, collaborativeAutoSave: true },
  3: { showInviteLink: false, canSaveDraft: false, canAdvance: true, collaborativeAutoSave: true },
  4: {
    showInviteLink: false,
    canSaveDraft: false,
    canAdvance: true,
    collaborativeAutoSave: true,
    requiresAllParticipantsDone: true,
  },
  5: {
    showInviteLink: false,
    canSaveDraft: false,
    canAdvance: false,
    collaborativeAutoSave: true,
    canFinalize: true,
    canExportPdf: true,
  },
};

export const phaseLabels = {
  1: 'Problem Vision Outline',
  2: 'Problem Vision Alignment',
  3: 'Research Problem Formulation',
  4: 'Research Problem Assessment',
  5: 'Go/Pivot/Abort Decision',
};

export function enumToPhaseNumber(enumPhase) {
  if (!enumPhase) return 1;
  if (typeof enumPhase === 'number') return enumPhase;
  const normalized = String(enumPhase).trim();
  if (/^\d+$/.test(normalized)) return Number(normalized);
  return Number(normalized.replace('F', ''));
}

export function phaseNumberToEnum(phaseNumber) {
  return `F${phaseNumber}`;
}
