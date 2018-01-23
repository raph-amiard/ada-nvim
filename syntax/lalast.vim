" Vim syntax file
" Language: lal ast

if exists("b:current_syntax")
  finish
endif

syn match  LalSlocRange "\v\d+:\d+-\d+:\d+"
syn match  LalTypeName "\v\u\w+"
syn match  LalField "\v[a-zA-Z]\w+:"

syn region LalString contains=@Spell start=+"+ skip=+""+ end=+"+

hi def link LalSlocRange    Number
hi def link LalTypeName     Statement
hi def link LalString       String
hi def link LalField        Identifier
" hi def link LalstateVarName         Function
" hi def link LalstateGenCodeVarName  Constant
" hi def link LalstateValue           String
" hi def link LalstateExprEvalValue   String
