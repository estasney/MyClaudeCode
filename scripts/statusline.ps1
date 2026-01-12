$data = $Input | ConvertFrom-Json
$model = $data.model.display_name
$cost = $data.cost.total_cost_usd
if ($cost -gt 0) {
    $cost_str = "{0:N2}" -f $cost
} else {
    $cost_str = "0"
}
Write-Host "$model ($cost_str)"