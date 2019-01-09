ada-nvim
========

This is an *extremely* alpha version of a neovim plugin for the Ada language.
It uses [libadalang](https://github.com/AdaCore/libadalang).


Key bindings
------------

<c-a><c-s>: Delete current node
<c-a><c-k>: Select parent node
<c-a><c-x>: go to definition
<c-a><c-h>: Highlight local references
<tab>: Indent current line (or selection in visual mode)

How to install using vim plug
-----------------------------

Add

```
    Plug 'path/to/ada-nvim/'
```

to your plugin section
