from collections import defaultdict
import libadalang as lal
import logging
from logging.handlers import RotatingFileHandler
import neovim
import os
import os.path as P
from tempfile import mktemp
import yaml

import lal_indenter


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler = RotatingFileHandler(P.join(P.expanduser("~"), '.ada_nvim.log'),
                                   'a', 1000000, 1)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

DEBUG = False


class Cmd(object):
    """
    Base class for a vim command.
    """

    def __init__(self, strn, *windows):
        """
        A vim command is a string plus a list of windows. Windows will be
        transformed into window numbers when the command is ran.
        """
        self.strn = strn
        self.windows = windows

    def render(self):
        return self.strn.format(*[w.number for w in self.windows])

    def run(self, nvim):
        if DEBUG:
            print("<Command '{}'>".format(self.render()))
        nvim.command(self.render())

    def __str__(self):
        return self.render()

    # Static methods that return vim commands

    @staticmethod
    def normal(command_strn):
        """
        Send normal commands to vim.

        :rtype: Cmd
        """
        return Cmd('execute "normal! {}"'.format(command_strn))

    @staticmethod
    def focus_on(window):
        """
        Return a Cmd that will focus on given nvim window.

        :rtype: Cmd
        """
        return Cmd("{}tabnext | {}wincmd w", window.tabpage, window)

    @staticmethod
    def center_on_line(line_no):
        """
        Will center the currently focused window on line line_no.

        :rtype: Cmd
        """
        return Cmds([str(line_no), Cmd.normal("z."), "redraw!"])

    @staticmethod
    def edit_file(file_name):
        """
        Edit given file.

        :rtype: Cmd
        """
        return Cmd("edit {}".format(file_name))

    @staticmethod
    def delete_range(start_line, start_col, end_line, end_col):
        return Cmd.normal(
            "{}G{}|v{}G{}|d".format(start_line, start_col, end_line, end_col)
        )


class Cmds(list, Cmd):
    """
    Cmd that represents a group of commands. Since it is also a vim command
    itself, it is composable easily.
    """

    def render(self):
        return " | ".join([str(cmd) for cmd in self])


def split(nvim, vertical=False, new_file=True):
    """
    Split windows, focus on the new window, and return the new window.

    :rtype: neovim.api.window.Window
    """
    cmds = Cmds(["vsplit" if vertical else "split"])
    if new_file:
        cmds.append("enew")
    cmds.run(nvim)

    return nvim.current.window


def vsplit(nvim, new_file=True):
    """
    Vertically split windows, focus on the new window, and return the new
    window.

    :rtype: neovim.api.window.Window
    """
    return split(nvim, True, new_file)


@neovim.plugin
class Main(object):

    def __init__(self, vim):
        self.vim = vim
        self._ast_window = None
        self._ast_shown = False
        self.files_versions = defaultdict(int)
        self.ast_version = ""
        self.ast_current_node = None
        Cmds([
            "set splitright",
            "set splitbelow",
            "set nocursorline",
            "highlight AdaNvimCurrentNode ctermbg=8 guibg=#445555",
            "highlight AdaNvimOccurences ctermbg=8 guibg=#66EE44",
        ]).run(self.vim)
        self.hl_source = self.vim.new_highlight_source()

        self._lal_context = None
        self.prj_file = None

    def create_project_from_file(self, file_name):
        prj = """
        project Default is
            for Source_Dirs use ("{}");
        end Default;
        """.format(P.dirname(file_name))

        with open("{}.gpr".format(mktemp()), 'w') as f:
            f.write(prj)
            return f.name

    def init_config(self, current_file):
        current_dir = os.getcwd()
        logger.info("In init_config, cwd={}".format(current_dir))

        yaml_path = ""
        while current_dir != "/":
            try_yaml_path = P.join(current_dir, "ada_nvim.yaml")
            logger.info("In init_config, cwd={}".format(current_dir))
            logger.info("In init_config, path={}".format(try_yaml_path))
            if P.isfile(try_yaml_path):
                yaml_path = try_yaml_path
                break
            else:
                current_dir = P.dirname(current_dir)

        if yaml_path:
            config = yaml.load(open(yaml_path))
            logger.info("In init_config, config = {}".format(config))
            self.prj_file = config.get('project_file', None)
            self.scenario_variables = config.get('scenario_variables')

        if not self.prj_file:
            assert current_file.endswith(('adb', 'ads'))
            self.prj_file = self.create_project_from_file(current_file)
            self.scenario_variables = {}

        logger.info("In init_config, analysis context created"
                    " with project {}".format(self.prj_file))

    def init_ada(self, current_file):
        self.init_config(current_file)
        self._lal_context = lal.AnalysisContext(
            unit_provider=lal.UnitProvider.for_project(
                self.prj_file, self.scenario_variables
            )
        )

    def lal_context(self):
        current_file = self.vim.eval('expand("%:p")')
        if not self._lal_context:
            self.init_ada(current_file)

        return self._lal_context

    def file_version(self, file_name):
        return "{}:{}".format(file_name, self.files_versions[file_name])

    def get_unit(self, file_name, content=None):
        if content:
            self.files_versions[file_name] += 1
            return self.lal_context().get_from_buffer(
                file_name, content, reparse=True
            )
        else:
            return self.lal_context().get_from_file(file_name)

    def current_unit(self):
        current_file = self.vim.eval('expand("%:p")')
        logger.info("In current_unit, file = {}".format(current_file))
        if not current_file.endswith(('adb', 'ads')):
            return
        return self.get_unit(current_file)

    def ast_window(self):
        current_window = self.vim.current.window
        if not self._ast_window:
            self._ast_window = vsplit(self.vim, True)
            Cmds([
                Cmd("set filetype=lalast"),
                Cmd.focus_on(current_window)
            ]).run(self.vim)
        return self._ast_window

    @neovim.autocmd('TextChangedI', pattern='*.ad?', eval='expand("%:p")')
    def autocmd_text_changed_i(self, file_name):
        self.autocmd_text_changed(file_name)

    @neovim.autocmd('TextChanged', pattern='*.ad?', eval='expand("%:p")')
    def autocmd_text_changed(self, file_name):
        logger.info("In autocmd_text_changed for file {}".format(file_name))
        self.ast_current_node = None
        unit = self.get_unit(file_name, "\n".join(self.vim.current.buffer[:]))
        logger.info("New unit's root: {}".format(unit.root))
        if self._ast_shown:
            self.ada_show_ast(reset_current_node=True)

    @neovim.autocmd('CursorMovedI', pattern='*.ad?', eval='expand("%:p")',
                    sync=True)
    def autocmd_cursor_moved_i(self, file_name):
        self.autocmd_cursor_moved(file_name)

    @neovim.autocmd('CursorMoved', pattern='*.ad?', eval='expand("%:p")',
                    sync=True)
    def autocmd_cursor_moved(self, file_name):
        logger.info("In autocmd_cursor_moved for file {}".format(file_name))
        if self._ast_shown:
            logger.info("22222222")
            self.ada_show_ast(reset_current_node=True)

    @neovim.function('AdaGetIndentNode')
    def ada_get_indent_node(self, args):
        unit = self.current_unit()

        if not unit.root:
            return

        line = self.vim.eval('line(".")')
        col = self.vim.eval('col(".")')
        self.vim.command('echo "Loc {} {}"'.format(line, col))
        current_node = unit.root.lookup(lal.Sloc(line, col))
        return current_node

    def open_file(self, file_name):
        if self.vim.current.buffer.name == file_name:
            return Cmds([])

        for w in self.vim.windows:
            if w.buffer.name == file_name:
                return Cmds([Cmd.focus_on(w)])

        return Cmds([Cmd("vsplit {}".format(file_name))])

    @neovim.function('AdaHighlightRefsInFile')
    def ada_highlight_refs_in_file(self, args):

        buf = self.vim.current.buffer
        buf.clear_highlight(self.hl_source)

        logger.info("In ada_go_to_def")
        node = self.ada_get_indent_node([])
        logger.info("Node = {}".format(node))

        if not node.is_a(lal.BaseId):
            return

        refd = node.p_referenced_decl
        logger.info("Refd = {}".format(refd))
        if refd:
            ids = node.unit.root.findall(
                lambda n: n.is_a(lal.BaseId)
                and n.text == refd.p_defining_name.text
            )
            logger.info("Ids = {}".format(ids))
            f_ids = []
            for id in ids:
                try:
                    cur_refd = id.p_referenced_decl
                except lal.PropertyError:
                    continue
                logger.info("Id = {}, Cur_Refd = {}, Refd = {}".format(
                    id, cur_refd, refd
                ))
                if cur_refd == refd:
                    f_ids.append(id)

            logger.info("F_Ids = {}".format(f_ids))
            for id in f_ids:
                sl = id.sloc_range
                buf.add_highlight(
                    "AdaNvimOccurences",
                    sl.start.line - 1,
                    sl.start.column - 1,
                    sl.end.column - 1,
                    src_id=self.hl_source
                )

    def indent_line(self, indent_level, line):
        strip_line = line.lstrip()
        nb_stripped = len(line) - len(strip_line)
        diff = indent_level - nb_stripped
        ret = (' ' * indent_level) + strip_line
        return ret, diff

    @neovim.function('AdaIndent')
    def ada_indent(self, args):

        unit = self.current_unit()
        logger.info("In ada_indent, args={}".format(args))
        start_line, end_line = args
        mmz_ctx = {}
        new_lines = []
        indent_buffer = lal_indenter.indent_all_file(
            unit, self.vim.current.buffer
        )

        for l in range(start_line, end_line + 1):
            # indent_level = lal_indenter.indent_for_line(
            #     l, self.vim.current.buffer, unit, mmz_ctx
            # )
            new_line, diff = self.indent_line(
                indent_buffer[l - 1], self.vim.current.buffer[l - 1]
            )
            new_lines.append(new_line)

        self.vim.current.buffer[start_line - 1:end_line] = new_lines

        if start_line == end_line and diff != 0:
            Cmd.normal("{}{}".format(
                abs(diff), "l" if diff > 0 else "h"
            )).run(self.vim)
        logger.info("Out of ada_indent")

    @neovim.function('AdaGoToDef')
    def ada_go_to_def(self, args):
        logger.info("In ada_go_to_def")
        node = self.ada_get_indent_node([])
        logger.info("Node = {}".format(node))
        refd = node.p_referenced_decl
        logger.info("Refd = {}".format(refd))
        if refd:
            cmds = self.open_file(refd.unit.filename)
            cmds.append(Cmd.center_on_line(refd.sloc_range.start.line))
            cmds.run(self.vim)

    @neovim.function('AdaSelectParentNode')
    def ada_select_parent_node(self, args):
        logger.info("In ada_select_parent_node, node = {}".format(
            self.ast_current_node
        ))

        if self.ast_current_node is not None:
            self.ast_current_node = self.ast_current_node.parent

        logger.info("node = {}".format(self.ast_current_node))
        self.ada_show_ast()

    @neovim.function('AdaDeleteCurrentNode')
    def ada_delete_current_node(self, args):
        logger.info("In ada_delete_current_node")

        if self.ast_current_node is not None:
            sl = self.ast_current_node.sloc_range
            Cmd.delete_range(sl.start.line, sl.start.column,
                             sl.end.line, sl.end.column - 1).run(self.vim)
        self.ada_show_ast([])

    @neovim.function('AdaShowAST')
    def ada_show_ast_public(self, args, reset_current_node=False):
        self.ada_show_ast(reset_current_node=reset_current_node)

    def ada_show_ast(self, reset_current_node=False):
        current_file = self.vim.eval('expand("%:p")')
        ast_version = self.file_version(current_file)
        self._ast_shown = True
        ast_window = self.ast_window()
        current_window = self.vim.current.window

        logger.info("In ada_show_ast, version = {}".format(ast_version))

        unit = self.get_unit(current_file)
        if not unit.root:
            ast_window.buffer[:] = ["incorrect parse"]
            Cmds([Cmd.focus_on(ast_window),
                  Cmd.center_on_line(1),
                  Cmd.focus_on(current_window)]).run(self.vim)
            return

        if ast_version != self.ast_version:
            logger.info("In ada_show_ast, recomputing buffer")
            ast_window.buffer[:] = unit.root.dump_str().splitlines()

        if self.ast_current_node is None or reset_current_node:
            current_node = self.ada_get_indent_node([])
            self.ast_current_node = current_node
        else:
            current_node = self.ast_current_node

        erepr = current_node.entity_repr[1:-1]
        ast_line = -1
        for i, l in enumerate(ast_window.buffer[:]):
            if erepr in l:
                ast_line = i + 1

        Cmds([
            Cmd.focus_on(ast_window),
            Cmd.center_on_line(ast_line),
            Cmd.focus_on(current_window)
        ]).run(self.vim)

        buf = current_window.buffer
        buf.clear_highlight(self.hl_source)
        sl = current_node.sloc_range
        logger.info("Sloc range: {}".format(sl))
        for line in range(sl.start.line, sl.end.line + 1):
            logger.info("Adding highlight {}:{} to {}:{}".format(
                line,
                sl.start.column if line == sl.start.line else 0,
                line,
                sl.end.column if line == sl.end.line else -1
            ))

            buf.add_highlight(
                "AdaNvimCurrentNode",
                line - 1,
                sl.start.column - 1 if line == sl.start.line else 0,
                sl.end.column - 1 if line == sl.end.line else -1,
                src_id=self.hl_source
            )

        ast_buf = ast_window.buffer
        ast_buf.clear_highlight(self.hl_source)
        ast_buf.add_highlight(
            "AdaNvimCurrentNode",
            ast_line - 1, 0, -1,
            src_id=self.hl_source
        )

        self.ast_version = self.file_version(current_file)
