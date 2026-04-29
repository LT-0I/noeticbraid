import { rootRoute } from './__root'
import { approvalsRoute } from './approvals'
import { indexRoute } from './index'
import { runsRoute } from './runs'
import { workspaceRoute } from './workspace'

export const routeTree = rootRoute.addChildren([
  indexRoute,
  workspaceRoute,
  runsRoute,
  approvalsRoute,
])
