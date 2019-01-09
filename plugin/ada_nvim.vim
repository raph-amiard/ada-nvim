autocmd FileType ada noremap <c-a><c-s> :call AdaDeleteCurrentNode()<CR>
autocmd FileType ada noremap <c-a><c-k> :call AdaSelectParentNode()<CR>
autocmd FileType ada noremap <c-a><c-x> :call AdaGoToDef()<CR>
autocmd FileType ada noremap <c-a><c-h> :call AdaHighlightRefsInFile()<CR>
autocmd FileType ada vnoremap <tab> :call AdaIndentWrapper()<CR>
autocmd FileType ada inoremap <tab> <esc>:call AdaIndentWrapper()<CR>$a
au FileType ada au CursorHold <buffer> call AdaHighlightRefsInFile()

if exists("g:adanvim#loaded") || v:version < 700
    finish
endif

let g:adanvim#loaded = '0.0.1' " version number

function! AdaIndentWrapper() range
    call AdaIndent(a:firstline, a:lastline)
endfunction
