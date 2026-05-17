import { rootRoute } from './__root'
import { accountsRoute } from './accounts'
import { approvalsRoute } from './approvals'
import { capabilitiesRoute } from './capabilities'
import { indexRoute } from './index'
import { platformDetailRoute, platformHistoryRoute, platformRoute } from './platform'
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
  accountsRoute,
  platformRoute,
  platformHistoryRoute,
  platformDetailRoute,
])
