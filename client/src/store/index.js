import { configureStore } from '@reduxjs/toolkit';
import workflowReducer from './workflowSlice';

export const store = configureStore({
  reducer: {
    workflow: workflowReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        // Ignore these action types in serializability checks
        ignoredActions: [
          'workflow/setConnectionError',
          'workflow/startNode',
          'workflow/completeNode',
          'workflow/errorNode',
        ],
      },
    }),
}); 