function AdaIndentWrapper() range
    call AdaIndent(a:firstline, a:lastline)
endfunction

autocmd FileType ada noremap <c-a><c-s> :call AdaDeleteCurrentNode()<CR>
autocmd FileType ada noremap <c-a><c-k> :call AdaSelectParentNode()<CR>
autocmd FileType ada noremap <c-a><c-x> :call AdaGoToDef()<CR>
autocmd FileType ada noremap <c-a><c-h> :call AdaHighlightRefsInFile()<CR>
autocmd FileType ada vnoremap <tab> :call AdaIndentWrapper()<CR>
