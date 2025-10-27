import React from 'react';
import ProcessingHistory from './ProcessingHistory';

// This component used to include the full detail/result UI. That detail view
// has been intentionally removed to avoid future confusion. The canonical
// processing list is `ProcessingHistory` and should be the single source of
// truth for listing and opening documents.

export default function ProcessingViewFixed(props) {
  return <ProcessingHistory {...props} />;
}
