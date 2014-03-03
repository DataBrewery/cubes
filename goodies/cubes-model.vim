" vim syntax highlighting of model.json files
"
" Use:
"
"   set syntax=cubes-model 
" 
"

runtime! syntax/javascript.vim
unlet b:current_syntax

syn match Keyword "\"model\"" display
syn match Keyword "\"cubes\"" display
syn match Keyword "\"dimensions\"" display
syn match Keyword "\"details\"" display
syn match Keyword "\"locale\"" display
syn match Keyword "\"public_dimensions\"" display
syn match Keyword "\"provider\"" display
syn match Keyword "\"source\"" display

syn match Keyword "\"levels\"" display
syn match Keyword "\"hierarchies\"" display
syn match Keyword "\"hierarchy\"" display
syn match Keyword "\"attributes\"" display
syn match Keyword "\"measures\"" display
syn match Keyword "\"template\"" display
syn match Keyword "\"cardinality\"" display
syn match Keyword "\"role\"" display
syn match Keyword "\"nonadditive\"" display
syn match Keyword "\"time\"" display

syn match Keyword "\"name\"" display
syn match Keyword "\"label\"" display
syn match Keyword "\"description\"" display
syn match Keyword "\"category\"" display
syn match Keyword "\"key\"" display
syn match Keyword "\"label_attribute\"" display
syn match Keyword "\"order_attribute\"" display
syn match Keyword "\"locales\"" display
syn match Keyword "\"info\"" display
syn match Keyword "\"options\"" display
syn match Keyword "\"order\"" display
syn match Keyword "\"aggregations\"" display
syn match Keyword "\"aggregates\"" display
syn match Keyword "\"measure\"" display
syn match Keyword "\"function\"" display
syn match Keyword "\"expression\"" display
syn match Keyword "\"formula\"" display

" Physical properties
syn match Keyword "\"store\"" display
syn match Keyword "\"browser\"" display
syn match Keyword "\"browser_options\"" display
syn match Keyword "\"fact\"" display

" Mappings
syn match Keyword "\"joins\"" display
syn match Keyword "\"mappings\"" display
syn match Keyword "\"master\"" display
syn match Keyword "\"detail\"" display
syn match Keyword "\"alias\"" display
syn match Keyword "\"method\"" display
syn match Keyword "\"match\"" display

syn match Keyword "\"column\"" display
syn match Keyword "\"table\"" display
syn match Keyword "\"schema\"" display
syn match Keyword "\"extract\"" display

