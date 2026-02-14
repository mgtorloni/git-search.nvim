local M = {}

local script_path = debug.getinfo(1, "S").source:sub(2)
local plugin_root = vim.fn.fnamemodify(script_path, ":h:h")
local is_win = vim.loop.os_uname().sysname:find("Windows")
local python_bin = is_win and ".venv/Scripts/python.exe" or ".venv/bin/python"
local python_executable = plugin_root .. "/" .. python_bin
local script_file = plugin_root .. "/python/main.py"

M.search = function()
	vim.ui.input({ prompt = "Describe the repo you need: " }, function(user_query)
		if not user_query or user_query == "" then return end

		require("telescope.pickers").new({}, {
			prompt_title = "GitHub Results for: " .. user_query,
			finder = require("telescope.finders").new_oneshot_job({
				python_executable,
				script_file,
				user_query
			}, {
				entry_maker = function(line)
					local status, repo = pcall(vim.json.decode, line)
					if not status or not repo then
						return { value = line, display = line, ordinal = line }
					end

					return {
						value = repo,
						display = string.format("%-40s  ★ %s", repo.full_name, repo.stargazers_count),
						ordinal = repo.full_name,
						url = repo.html_url
					}
				end
			}),
			sorter = require("telescope.config").values.generic_sorter({}),

			attach_mappings = function(prompt_bufnr, map)
				local actions = require("telescope.actions")
				local action_state = require("telescope.actions.state")

				actions.select_default:replace(function()
					actions.close(prompt_bufnr)
					local selection = action_state.get_selected_entry()
					if selection and selection.url then
						vim.ui.open(selection.url)
					end
				end)
				return true
			end,
		}):find()
	end)
end

return M
