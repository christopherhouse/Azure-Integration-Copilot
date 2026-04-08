/// Shared helpers for working with System.Text.Json elements.
///
/// These helpers exist to disambiguate the overloaded JsonElement.TryGetProperty,
/// which has three overloads (string, ReadOnlySpan<char>, ReadOnlySpan<byte>) that
/// the F# compiler cannot resolve from a string literal alone.
module IntegrisightWorkerAnalysis.JsonHelpers

open System.Text.Json

/// Attempt to find a property by name. Uses the explicit byref overload so F# can
/// unambiguously resolve the string overload.
let inline tryGetProp (name: string) (el: JsonElement) : bool * JsonElement =
    let mutable v = Unchecked.defaultof<JsonElement>
    let found = el.TryGetProperty(name, &v)
    found, v

/// Get a string property or return the default value.
let inline getString (name: string) (defaultValue: string) (el: JsonElement) : string =
    match tryGetProp name el with
    | true, v when v.ValueKind <> JsonValueKind.Null -> v.GetString() |> Option.ofObj |> Option.defaultValue defaultValue
    | _ -> defaultValue

/// Get an optional string property.
let inline getStringOpt (name: string) (el: JsonElement) : string option =
    match tryGetProp name el with
    | true, v when v.ValueKind <> JsonValueKind.Null -> v.GetString() |> Option.ofObj
    | _ -> None

/// Get an int property or return the default value.
let inline getInt (name: string) (defaultValue: int) (el: JsonElement) : int =
    match tryGetProp name el with
    | true, v when v.ValueKind = JsonValueKind.Number -> v.GetInt32()
    | _ -> defaultValue

/// Get a float property or return the default value.
let inline getDouble (name: string) (defaultValue: float) (el: JsonElement) : float =
    match tryGetProp name el with
    | true, v when v.ValueKind = JsonValueKind.Number -> v.GetDouble()
    | _ -> defaultValue

/// Get a bool property or return the default value.
let inline getBool (name: string) (defaultValue: bool) (el: JsonElement) : bool =
    match tryGetProp name el with
    | true, v when v.ValueKind = JsonValueKind.True -> true
    | true, v when v.ValueKind = JsonValueKind.False -> false
    | _ -> defaultValue

/// Get a JsonElement sub-property or return a null/undefined element.
let inline getElement (name: string) (el: JsonElement) : JsonElement option =
    match tryGetProp name el with
    | true, v when v.ValueKind <> JsonValueKind.Null -> Some v
    | _ -> None
