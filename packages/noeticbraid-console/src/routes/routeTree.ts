import { rootRoute } from './__root'
import { approvalsRoute } from './approvals'
import { capabilitiesRoute } from './capabilities'
import { indexRoute } from './index'
import { omcIngestRoute } from './projects/omc-ingest'
import { runsRoute } from './runs'
import { workspaceRoute } from './workspace'

export const routeTree = rootRoute.addChildren([
  indexRoute,
  workspaceRoute,
  runsRoute,
  approvalsRoute,
  omcIngestRoute,
  capabilitiesRoute,
])
