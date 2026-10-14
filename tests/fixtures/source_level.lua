-- MoonVeil Obfuscator v1.4.5 — synthetic fixture; no network or Roblox APIs.
local alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
local environment = getfenv()
local function decode(value, key)
    local result = {}
    for index = 1, #value do
        result[index] = string.char(bit32.bxor(string.byte(value, index), string.byte(key, ((index - 1) % #key) + 1)))
    end
    return table.concat(result)
end
print(decode('\104\101\108\108\111', '\000'))
print(decode('\119\111\114\108\100', '\000'))
print(decode('\109\111\111\110', '\000'))
print(decode('\118\101\105\108', '\000'))
print(decode('\115\111\117\114\99\101', '\000'))
print(decode('\115\116\114\105\110\103', '\000'))
print(decode('\112\114\111\98\101', '\000'))
print(decode('\102\105\110\105\115\104', '\000'))
print(6 * 7)
