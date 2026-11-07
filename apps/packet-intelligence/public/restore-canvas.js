// Restore the pre-board canvas once for browsers that received the separated UI.
if(!S.originalCanvasRestored){
 if(S.decisionBoardsVersion||S.unifiedCanvasVersion){
  S.layouts.overview=structuredClone(S.layouts.saved_overview||defaultLayouts.overview);
  S.layouts.operators=structuredClone(defaultLayouts.operators);
  S.layouts.readiness=structuredClone(defaultLayouts.readiness);
  for(const key of ['market','demand','structure','outreach'])delete S.layouts[key];
  S.board='overview';S.view='canvas';S.dataset='operators';
 }
 S.originalCanvasRestored=true;
}
for(const key of ['market','demand','structure','outreach'])delete boardNames[key];
Object.assign(boardNames,{overview:'Research overview',operators:'Operator landscape',readiness:'Flight readiness',custom:'My canvas'});
if(!S.layouts[S.board])S.board='overview';
persist();
