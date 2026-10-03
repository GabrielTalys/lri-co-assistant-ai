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
  5: { showInviteLink: false, canSaveDraft: false, canAdvance: false, collaborativeAutoSave: true },
};

export const phaseLabels = {
  1: 'Problem Vision Outline',
  2: 'Problem Vision Alignment',
  3: 'Research Problem Formulation',
  4: 'Research Problem Assessment',
  5: 'Go/Pivot/Abort Decision',
};
